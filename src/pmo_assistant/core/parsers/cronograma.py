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
from datetime import date

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


def parsear_cronograma(texto: str, projeto_id: int, nome_projeto: str) -> Cronograma:
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
