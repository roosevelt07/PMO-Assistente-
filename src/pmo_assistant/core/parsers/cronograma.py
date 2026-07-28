"""Parser determinístico de cronograma MS Project exportado em PDF.

SEM LLM. Validado contra dois layouts reais Netcon:
- Atiaia (simples):      Id Nome %concl Início Término
- Charqueadas (baseline): Id Nome %concl %esperado BLini BLterm Início Término RealIni RealTerm

DESAFIOS RESOLVIDOS (vistos no texto real do pypdf):
1. Nomes longos quebram em 2-3 linhas; só a última traz %/datas. -> buffer de nome.
2. Datas vêm coladas sem espaço: 'Qua 03/12/25Qui 09/07/26'. -> regex global de datas.
3. % pode vir colado ao nome: 'Incêndio100%'. -> regex acha o % em qualquer posição.
4. Páginas só-Gantt (pg 6+) não têm linhas com %. -> ignoradas naturalmente.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

from loguru import logger

from pmo_assistant.core.models import Cronograma, TarefaCronograma

# data com dia-da-semana opcional colado ou não: 'Qua 03/12/25' ou '03/12/26'
_DATA_RE = re.compile(r"(?:[A-Za-zÁ-ú]{3}\s*)?(\d{2}/\d{2}/\d{2,4})")
_PCT_RE = re.compile(r"(\d{1,3})%")
_ID_INICIO_RE = re.compile(r"^\s*(\d+)\s+(.+)$")
_ND_RE = re.compile(r"\bND\b")

_FASES = (
    "INICIALIZAÇÃO",
    "PLANEJAMENTO",
    "SUPRIMENTOS/FORNECEDOR",
    "SUPRIMENTOS",
    "EXECUÇÃO",
    "ENCERRAMENTO",
    "FASE",
    "FAZE",
    "COMPRA DE",
)

# --- Layout B — Dashboard Executivo (Tripla, Usina Santo Antônio) ---
# IDs decimais ('1.1', '2.1') não casam em _ID_INICIO_RE (\d+ seguido de espaço),
# por isso o layout MS Project silenciosamente não extrai nada desse formato.
_ID_DECIMAL_RE = re.compile(r"^\s*(\d+(?:\.\d+)+)\s+(.+)$")
_STATUS_DASHBOARD_RE = re.compile(r"(Conclu[ií]do|A\s+Iniciar|Em\s+Andamento)", re.IGNORECASE)
# Diferente de _DATA_RE (Layout A), sem prefixo de dia-da-semana opcional: nesse
# layout esse grupo opcional acabava "comendo" as últimas letras da palavra
# anterior quando colada num espaço antes da data (ex: 'arquitetura 01/01/26').
_DATA_SIMPLES_RE = re.compile(r"\d{2}/\d{2}/\d{2,4}")
_PCT_CONCLUIDA = 100.0
_PCT_EM_ANDAMENTO = 50.0
_PCT_A_INICIAR = 0.0


def detectar_layout(texto: str) -> str:
    """Detecta o formato do PDF de cronograma pelo conteúdo textual.

    MS Project: contém cabeçalhos específicos em português do MS Project.
    Dashboard Executivo: contém estrutura de resumo com totais e status literais.
    """
    if "% Expected" in texto or "Início da Linha de Base" in texto:
        return "ms_project"
    if "A Iniciar" in texto and "Concluído" in texto and "Resp." in texto:
        return "dashboard_executivo"
    return "desconhecido"


def parsear_cronograma(texto: str, projeto_id: int, nome_projeto: str) -> Cronograma:
    """Extrai tarefas do texto de um cronograma PDF, detectando o layout primeiro."""
    layout = detectar_layout(texto)
    if layout == "ms_project":
        return _parsear_ms_project(texto, projeto_id, nome_projeto)
    if layout == "dashboard_executivo":
        return _parsear_dashboard_executivo(texto, projeto_id, nome_projeto)
    logger.warning(
        "Layout de cronograma não reconhecido | projeto={} — tentando MS Project como fallback",
        nome_projeto,
    )
    return _parsear_ms_project(texto, projeto_id, nome_projeto)


def _parsear_ms_project(texto: str, projeto_id: int, nome_projeto: str) -> Cronograma:
    """Extrai tarefas do texto de um cronograma PDF (todas as páginas concatenadas)."""
    data_ref = _extrair_data_referencia(texto)
    tarefas: list[TarefaCronograma] = []

    # buffer para acumular linhas de nome quebrado
    id_buffer: int | None = None
    nome_buffer: str = ""

    for raw in texto.splitlines():
        linha = raw.rstrip()
        if not linha.strip():
            continue

        tem_pct = bool(_PCT_RE.search(linha))
        m_id = _ID_INICIO_RE.match(linha)

        if m_id and tem_pct:
            # linha completa numa só: fecha buffer pendente e processa esta
            id_buffer, nome_buffer = None, ""
            t = _montar_tarefa(int(m_id.group(1)), m_id.group(2))
            if t:
                tarefas.append(t)
        elif m_id and not tem_pct:
            # início de tarefa com nome que vai quebrar -> abre buffer
            id_buffer = int(m_id.group(1))
            nome_buffer = m_id.group(2).strip()
        elif not m_id and tem_pct and id_buffer is not None:
            # linha de continuação que traz os %/datas -> fecha o buffer
            t = _montar_tarefa(id_buffer, nome_buffer + " " + linha.strip())
            if t:
                tarefas.append(t)
            id_buffer, nome_buffer = None, ""
        elif not m_id and not tem_pct and id_buffer is not None:
            # linha do meio de um nome longo -> acumula
            nome_buffer += " " + linha.strip()
        # demais casos (cabeçalho, legenda, gantt): ignora

    logger.info(
        "cronograma parseado | projeto={} tarefas={} atrasadas={}",
        nome_projeto,
        len(tarefas),
        sum(1 for t in tarefas if t.atrasada),
    )
    return Cronograma(
        projeto_id=projeto_id,
        nome_projeto=nome_projeto,
        data_referencia=data_ref,
        tarefas=tarefas,
    )


def _montar_tarefa(id_tarefa: int, corpo: str) -> TarefaCronograma | None:
    """Monta TarefaCronograma a partir do Id + corpo (nome + %/datas)."""
    pcts = _PCT_RE.findall(corpo)
    if not pcts:
        return None

    # nome = trecho antes do primeiro %
    pos_pct = corpo.find(pcts[0] + "%")
    nome = corpo[:pos_pct].strip().rstrip("-").strip()
    if not nome or len(nome) < 2:
        return None

    cauda = corpo[pos_pct:]
    [_parse_data(d) for d in _DATA_RE.findall(cauda)]

    # Inserir None nas posições onde aparece 'ND' para manter alinhamento posicional.
    # Estratégia: tokenizar a cauda em datas e NDs na ordem em que aparecem.
    seq: list[date | None] = []
    for tok in re.finditer(r"(\d{2}/\d{2}/\d{2,4})|(\bND\b)", cauda):
        if tok.group(1):
            seq.append(_parse_data(tok.group(1)))
        else:
            seq.append(None)

    pct_concl = float(pcts[0])
    pct_esp = float(pcts[1]) if len(pcts) >= 2 else None

    inicio_bl = termino_bl = inicio = termino = inicio_real = termino_real = None
    if pct_esp is not None:  # layout baseline (Charqueadas)
        inicio_bl = seq[0] if len(seq) > 0 else None
        termino_bl = seq[1] if len(seq) > 1 else None
        inicio = seq[2] if len(seq) > 2 else None
        termino = seq[3] if len(seq) > 3 else None
        inicio_real = seq[4] if len(seq) > 4 else None
        termino_real = seq[5] if len(seq) > 5 else None
    else:  # layout simples (Atiaia)
        inicio = seq[0] if len(seq) > 0 else None
        termino = seq[1] if len(seq) > 1 else None

    return TarefaCronograma(
        id_tarefa=id_tarefa,
        nome=nome,
        percentual_concluido=min(pct_concl, 100.0),
        percentual_esperado=min(pct_esp, 100.0) if pct_esp is not None else None,
        inicio_baseline=inicio_bl,
        termino_baseline=termino_bl,
        inicio=inicio,
        termino=termino,
        inicio_real=inicio_real,
        termino_real=termino_real,
        eh_resumo=_eh_fase_resumo(nome),
    )


def _eh_fase_resumo(nome: str) -> bool:
    u = nome.upper()
    if any(u.startswith(f) for f in _FASES):
        return True
    # nome todo em caixa alta e curto = linha-resumo (ex: 'SE CHARQUEADAS')
    return u == nome and len(nome.split()) <= 4 and len(nome) > 3


def _parse_data(s: str) -> date | None:
    try:
        d, m, a = (int(x) for x in s.split("/"))
        if a < 100:
            a += 2000
        return date(a, m, d)
    except (ValueError, IndexError):
        return None


def _extrair_data_referencia(texto: str) -> date | None:
    m = re.search(r"Data:\s*(?:[A-Za-zÁ-ú]{3}\s*)?(\d{2}/\d{2}/\d{2,4})", texto)
    return _parse_data(m.group(1)) if m else None


def _extrair_resumo_dashboard(texto: str) -> dict[str, float]:
    """Extrai totais do bloco de resumo do Dashboard Executivo.

    Busca padrões como 'Concluído NNN MM%' e 'Total Geral NNN'. Robusto a
    variações de emoji e espaçamento entre o rótulo e o número.
    """
    resultado = {
        "total": 0.0,
        "concluidas": 0.0,
        "a_iniciar": 0.0,
        "percentual": 0.0,
    }

    m = re.search(r"Total\s+Geral\s+(\d+)", texto, re.IGNORECASE)
    if m:
        resultado["total"] = float(m.group(1))

    m = re.search(r"Conclu[ií]d[ao]\s+(\d+)\s+(\d+)%", texto, re.IGNORECASE)
    if m:
        resultado["concluidas"] = float(m.group(1))
        resultado["percentual"] = float(m.group(2))

    m = re.search(r"A\s+Iniciar\s+(\d+)", texto, re.IGNORECASE)
    if m:
        resultado["a_iniciar"] = float(m.group(1))

    return resultado


def _parsear_dashboard_executivo(texto: str, projeto_id: int, nome_projeto: str) -> Cronograma:
    """Extrai tarefas do Layout B (Dashboard Executivo — Tripla, Usina Santo Antônio).

    Sem baseline: percentual_esperado fica sempre None. O critério de atraso é
    literal (termino já passou de hoje e a tarefa não está concluída) — ver
    _montar_tarefa_dashboard.
    """
    data_ref = _extrair_data_referencia(texto)
    resumo = _extrair_resumo_dashboard(texto)
    tarefas: list[TarefaCronograma] = []

    id_buffer: str | None = None
    corpo_buffer = ""
    proximo_id = 2  # id_tarefa=1 é reservado para a linha-resumo sintética

    for raw in texto.splitlines():
        linha = raw.rstrip()
        if not linha.strip():
            continue

        tem_status = bool(_STATUS_DASHBOARD_RE.search(linha))
        m_id = _ID_DECIMAL_RE.match(linha)

        if m_id and tem_status:
            id_buffer, corpo_buffer = None, ""
            t = _montar_tarefa_dashboard(proximo_id, m_id.group(2))
            if t:
                tarefas.append(t)
                proximo_id += 1
        elif m_id and not tem_status:
            id_buffer = m_id.group(1)
            corpo_buffer = m_id.group(2).strip()
        elif not m_id and tem_status and id_buffer is not None:
            t = _montar_tarefa_dashboard(proximo_id, corpo_buffer + " " + linha.strip())
            if t:
                tarefas.append(t)
                proximo_id += 1
            id_buffer, corpo_buffer = None, ""
        elif not m_id and not tem_status and id_buffer is not None:
            corpo_buffer += " " + linha.strip()
        # demais casos (cabeçalho, legenda, bloco de resumo): ignora

    resumo_sintetico = TarefaCronograma(
        id_tarefa=1,
        nome=nome_projeto,
        percentual_concluido=resumo["percentual"],
        percentual_esperado=None,  # Layout B não tem baseline geral — evita falso ATRASADO
        eh_resumo=True,
    )
    tarefas.insert(0, resumo_sintetico)

    logger.info(
        "cronograma parseado (dashboard_executivo) | projeto={} tarefas={} atrasadas={}",
        nome_projeto,
        len(tarefas),
        sum(1 for t in tarefas if t.atrasada),
    )
    return Cronograma(
        projeto_id=projeto_id,
        nome_projeto=nome_projeto,
        data_referencia=data_ref,
        tarefas=tarefas,
    )


def _montar_tarefa_dashboard(id_tarefa: int, corpo: str) -> TarefaCronograma | None:
    """Monta TarefaCronograma a partir do Id decimal + corpo (nome + resp/datas/status)."""
    m_status = _STATUS_DASHBOARD_RE.search(corpo)
    if not m_status:
        return None

    m_primeira_data = _DATA_SIMPLES_RE.search(corpo)
    if not m_primeira_data:
        return None

    nome = corpo[: m_primeira_data.start()].strip().rstrip("-").strip()
    if not nome or len(nome) < 2:
        return None

    datas = [_parse_data(d) for d in _DATA_SIMPLES_RE.findall(corpo[m_primeira_data.start() :])]
    inicio = datas[0] if len(datas) > 0 else None
    termino = datas[1] if len(datas) > 1 else None

    status_norm = re.sub(r"\s+", " ", m_status.group(1)).strip().lower()
    if status_norm.startswith("conclu"):
        pct_concl = _PCT_CONCLUIDA
        inicio_real = inicio
        termino_real = termino
    elif status_norm.startswith("a iniciar"):
        pct_concl = _PCT_A_INICIAR
        inicio_real = None
        termino_real = None
    else:  # em andamento
        pct_concl = _PCT_EM_ANDAMENTO
        inicio_real = inicio
        termino_real = None

    # Sem baseline, o atraso é literal: prazo estourado e ainda não concluída.
    # Truque local ao parser (não altera o schema): define uma baseline sintética
    # um dia antes do término real só para acionar o computed_field `atrasada`
    # (termino > termino_baseline). Não afeta o Layout A.
    termino_baseline = None
    if termino is not None and termino < date.today() and pct_concl < _PCT_CONCLUIDA:
        termino_baseline = termino - timedelta(days=1)

    return TarefaCronograma(
        id_tarefa=id_tarefa,
        nome=nome,
        percentual_concluido=pct_concl,
        percentual_esperado=None,
        termino_baseline=termino_baseline,
        inicio=inicio,
        termino=termino,
        inicio_real=inicio_real,
        termino_real=termino_real,
        eh_resumo=False,
    )
