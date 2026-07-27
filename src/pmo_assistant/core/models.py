"""Schemas de domínio. Fonte canônica de verdade.

Três blocos, cada um amarrado a um objetivo do TCC:
- AcaoExtraida / ResultadoExtracao  -> extração de ações de atas (LLM)
- TarefaCronograma / Cronograma      -> parsing de cronograma MS Project (determinístico)
- SaudeProjeto                       -> indicador cruzado para apoio à decisão

Mudou um schema? Rode a migration Alembic correspondente.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

# ---------------------------------------------------------------------------
# Bloco comum
# ---------------------------------------------------------------------------


class TipoDocumento(StrEnum):
    KICKOFF = "kickoff"
    ACOMPANHAMENTO = "acompanhamento"
    HANDOVER = "handover"
    STATUS_REPORT = "status_report"
    CRONOGRAMA = "cronograma"
    OUTRO = "outro"


# ---------------------------------------------------------------------------
# Bloco 1 — Ações extraídas de atas (via LLM com tool use)
# ---------------------------------------------------------------------------


class StatusAcao(StrEnum):
    NAO_INICIADA = "nao_iniciada"
    EM_ANDAMENTO = "em_andamento"
    CONCLUIDA = "concluida"
    ATRASADA = "atrasada"
    INDETERMINADO = "indeterminado"


class AcaoExtraida(BaseModel):
    """Ação identificada pelo LLM a partir de uma ata. Schema do tool use."""

    model_config = ConfigDict(str_strip_whitespace=True)

    descricao: str = Field(
        ...,
        min_length=5,
        max_length=500,
        description="Descrição clara e auto-contida da ação. Inclua o objeto, não só o verbo.",
    )
    responsavel: str | None = Field(
        None,
        max_length=120,
        description=(
            "Nome ou empresa responsável (ex: 'NETCON', 'Grantel', 'João'). "
            "Null se não identificável."
        ),
    )
    prazo: date | None = Field(
        None,
        description="Data limite ISO YYYY-MM-DD. Null se não houver prazo explícito na ata.",
    )
    status: StatusAcao = Field(
        StatusAcao.INDETERMINADO,
        description="Status inferido. INDETERMINADO se não houver evidência.",
    )
    contexto_origem: str = Field(
        ...,
        max_length=300,
        description=(
            "Trecho LITERAL da ata (até 300 chars) que justifica a extração. Sem paráfrase."
        ),
    )
    confianca: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confiança 0-1. Use <0.5 quando ambíguo ou sem responsável claro.",
    )

    @field_validator("descricao")
    @classmethod
    def _descricao_nao_vazia(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("descricao vazia após strip")
        return v


class ResultadoExtracao(BaseModel):
    """Resultado completo da extração sobre uma ata."""

    acoes: list[AcaoExtraida] = Field(default_factory=list)
    resumo_documento: str = Field(
        ..., max_length=1000, description="Resumo executivo da ata em até 5 frases."
    )


# ---------------------------------------------------------------------------
# Bloco 2 — Cronograma (parsing determinístico, SEM LLM)
# ---------------------------------------------------------------------------

_PCT_COMPLETO = 100.0  # percentual que marca uma tarefa como totalmente concluída


class TarefaCronograma(BaseModel):
    """Linha de um cronograma MS Project exportado em PDF.

    'ND' (não definido) no PDF vira None nas datas reais.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    id_tarefa: int
    nome: str = Field(..., min_length=1)
    percentual_concluido: float = Field(..., ge=0.0, le=100.0)
    percentual_esperado: float | None = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Só presente em cronogramas com baseline (ex: Charqueadas).",
    )
    inicio_baseline: date | None = None
    termino_baseline: date | None = None
    inicio: date | None = None
    termino: date | None = None
    inicio_real: date | None = None
    termino_real: date | None = None
    eh_resumo: bool = Field(
        False, description="True para linhas-resumo de fase (PLANEJAMENTO, SUPRIMENTOS, etc.)."
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def atrasada(self) -> bool:
        """Tarefa atrasada: término real estourou baseline, ou avanço abaixo do esperado.

        Regra derivada dos cronogramas reais Netcon. Linhas-resumo não contam
        como atraso individual (são agregados).
        """
        if self.eh_resumo:
            return False
        if (
            self.percentual_esperado is not None
            and self.percentual_concluido < self.percentual_esperado
        ):
            return True
        return bool(
            self.termino is not None
            and self.termino_baseline is not None
            and self.termino > self.termino_baseline
            and self.percentual_concluido < _PCT_COMPLETO
        )


class Cronograma(BaseModel):
    """Cronograma completo de um projeto."""

    projeto_id: int
    nome_projeto: str
    data_referencia: date | None = Field(None, description="Data do snapshot (rodapé do PDF).")
    tarefas: list[TarefaCronograma] = Field(default_factory=list)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_atrasadas(self) -> int:
        return sum(1 for t in self.tarefas if t.atrasada)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def percentual_geral(self) -> float | None:
        """% concluído da linha-resumo de nível 1 (o projeto inteiro), se houver."""
        for t in self.tarefas:
            if t.id_tarefa == 1:
                return t.percentual_concluido
        return None


# ---------------------------------------------------------------------------
# Bloco 3 — Saúde do projeto (cruzamento para apoio à decisão)
# ---------------------------------------------------------------------------


class NivelSaude(StrEnum):
    NO_PRAZO = "no_prazo"
    EM_RISCO = "em_risco"
    ATRASADO = "atrasado"
    SEM_DADOS = "sem_dados"


class SaudeProjeto(BaseModel):
    """Indicador de saúde derivado de cronograma + ações pendentes."""

    projeto_id: int
    nome_projeto: str
    nivel: NivelSaude
    percentual_concluido: float | None = None
    percentual_esperado: float | None = None
    tarefas_atrasadas: int = 0
    acoes_pendentes: int = 0
    justificativa: str = Field(..., max_length=500)


# ---------------------------------------------------------------------------
# Bloco 4 — Chat RAG (síntese de trechos recuperados por busca full-text)
# ---------------------------------------------------------------------------


class RespostaChat(BaseModel):
    """Resposta do chat, fundamentada nos trechos recuperados via FTS5. Schema do tool use."""

    resposta: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description=(
            "Resposta em português, citando trechos literais entre aspas quando afirma "
            "algo. 'Não encontrei informação suficiente' quando os trechos não cobrem a "
            "pergunta."
        ),
    )
    fontes: list[str] = Field(
        default_factory=list,
        description="Trechos literais usados para fundamentar a resposta.",
    )
    confianca: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confiança 0-1 de que a resposta está corretamente fundamentada nos trechos.",
    )


# ---------------------------------------------------------------------------
# Entidades de persistência (metadados)
# ---------------------------------------------------------------------------


class Projeto(BaseModel):
    id: int | None = None
    nome: str = Field(..., min_length=1, max_length=200)
    cliente: str | None = Field(None, max_length=200)
    criado_em: datetime = Field(default_factory=datetime.utcnow)


class DocumentoEntrada(BaseModel):
    nome_arquivo: str
    tipo: TipoDocumento
    projeto_id: int
    enviado_em: datetime = Field(default_factory=datetime.utcnow)
    conteudo_bruto: str
