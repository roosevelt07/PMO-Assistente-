"""Testes de extrator de ações, models e avaliação de saúde."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from pmo_assistant.core.extractors.acoes import extrair_acoes
from pmo_assistant.core.models import (
    AcaoExtraida,
    Cronograma,
    NivelSaude,
    StatusAcao,
    TarefaCronograma,
    TipoDocumento,
)
from pmo_assistant.core.saude import avaliar_saude

CONTEUDO = "Ata de KickOff Charqueadas. " * 10  # > 100 chars


def test_extrair_acoes_feliz(fake_llm):
    res = extrair_acoes(CONTEUDO, TipoDocumento.KICKOFF, "ata.pdf", fake_llm)
    assert len(res.acoes) == 1
    assert res.acoes[0].responsavel == "NETCON"
    assert res.acoes[0].prazo == date(2025, 12, 3)
    assert "kickoff" in fake_llm.chamadas[0]["user"]


def test_extrair_acoes_conteudo_curto(fake_llm):
    with pytest.raises(ValueError, match="curto"):
        extrair_acoes("oi", TipoDocumento.KICKOFF, "x.pdf", fake_llm)


def test_acao_descricao_curta_rejeita():
    with pytest.raises(ValidationError):
        AcaoExtraida(descricao="oi", contexto_origem="x", confianca=0.5)


def test_acao_minima_valida():
    acao = AcaoExtraida(
        descricao="Enviar planilha de custos atualizada para a diretoria",
        contexto_origem="Trecho da ata mencionando o envio",
        confianca=0.85,
    )
    assert acao.status == StatusAcao.INDETERMINADO
    assert acao.responsavel is None
    assert acao.prazo is None


def test_acao_completa():
    acao = AcaoExtraida(
        descricao="Revisar contrato com fornecedor",
        responsavel="Maria",
        prazo=date(2026, 7, 30),
        status=StatusAcao.EM_ANDAMENTO,
        contexto_origem="Maria ficou responsável pela revisão",
        confianca=0.9,
    )
    assert acao.prazo.month == 7


def test_confianca_fora_de_intervalo_rejeita():
    with pytest.raises(ValidationError):
        AcaoExtraida(
            descricao="Ação válida com descrição suficiente",
            contexto_origem="trecho",
            confianca=1.5,
        )


def test_extrair_acoes_payload_invalido_levanta(fake_llm):
    fake_llm.payload = {"acoes": [{"descricao": ""}], "resumo_documento": "ok"}
    with pytest.raises(ValidationError):
        extrair_acoes(CONTEUDO, TipoDocumento.KICKOFF, "x.pdf", fake_llm)


def test_extrair_acoes_kickoff_duas_acoes(fake_llm):
    fake_llm.payload = {
        "acoes": [
            {
                "descricao": "Enviar cronograma executivo do projeto",
                "responsavel": "NETCON",
                "prazo": "2025-12-03",
                "status": "nao_iniciada",
                "contexto_origem": "Netcon informou que enviará o cronograma executivo, até 03/12.",
                "confianca": 0.9,
            },
            {
                "descricao": "Definir escopo detalhado da fase de suprimentos",
                "responsavel": None,
                "prazo": None,
                "status": "indeterminado",
                "contexto_origem": "Ficou pendente de definição em reunião futura.",
                "confianca": 0.4,
            },
        ],
        "resumo_documento": "Ata de KickOff do projeto Charqueadas.",
    }

    res = extrair_acoes(CONTEUDO, TipoDocumento.KICKOFF, "ata_kickoff.pdf", fake_llm)

    assert len(res.acoes) == 2
    a1, a2 = res.acoes
    assert isinstance(a1, AcaoExtraida)
    assert isinstance(a2, AcaoExtraida)
    assert a1.responsavel == "NETCON"
    assert a1.prazo == date(2025, 12, 3)
    assert a1.status == StatusAcao.NAO_INICIADA
    assert a2.responsavel is None
    assert a2.prazo is None
    assert a2.status == StatusAcao.INDETERMINADO


def test_tarefa_atrasada_por_baseline():
    t = TarefaCronograma(
        id_tarefa=1, nome="X", percentual_concluido=50.0,
        termino=date(2026, 8, 1), termino_baseline=date(2026, 7, 1),
    )
    assert t.atrasada


def test_tarefa_resumo_nunca_atrasada():
    t = TarefaCronograma(
        id_tarefa=1, nome="PLANEJAMENTO", percentual_concluido=10.0,
        percentual_esperado=90.0, eh_resumo=True,
    )
    assert not t.atrasada


def test_saude_atrasado():
    cr = Cronograma(
        projeto_id=1, nome_projeto="P",
        tarefas=[
            TarefaCronograma(
                id_tarefa=1, nome="P", percentual_concluido=70.0, percentual_esperado=95.0,
                termino=date(2026, 8, 11), termino_baseline=date(2026, 7, 9),
            )
        ],
    )
    s = avaliar_saude(cr)
    assert s.nivel == NivelSaude.ATRASADO


def test_saude_sem_dados():
    cr = Cronograma(projeto_id=1, nome_projeto="P", tarefas=[])
    s = avaliar_saude(cr)
    assert s.nivel == NivelSaude.SEM_DADOS


def test_saude_atrasado_end_to_end():
    cr = Cronograma(
        projeto_id=1,
        nome_projeto="Charqueadas TLC",
        tarefas=[
            TarefaCronograma(
                id_tarefa=1,
                nome="GRANTEL-AXIA SUL-AMPL SE CHARQUEADAS (TLC)",
                percentual_concluido=94.0,
                percentual_esperado=99.0,
                termino=date(2026, 8, 11),
                termino_baseline=date(2026, 7, 9),
            ),
        ],
    )

    saude = avaliar_saude(cr, [StatusAcao.NAO_INICIADA, StatusAcao.EM_ANDAMENTO])

    assert saude.nivel == NivelSaude.ATRASADO
    assert saude.acoes_pendentes == 2
    assert "término impactado" in saude.justificativa


def test_saude_conta_acoes_pendentes():
    cr = Cronograma(
        projeto_id=1, nome_projeto="P",
        tarefas=[TarefaCronograma(id_tarefa=1, nome="P", percentual_concluido=100.0, percentual_esperado=100.0)],
    )
    s = avaliar_saude(cr, [StatusAcao.NAO_INICIADA, StatusAcao.CONCLUIDA])
    assert s.acoes_pendentes == 1
