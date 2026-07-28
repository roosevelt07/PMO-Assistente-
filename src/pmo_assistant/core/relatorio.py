"""Lógica de agregação para relatórios. Zero I/O — testável sem banco/arquivo.

Consome Cronograma (objeto em memória), nunca toca infra/. Fonte dos dados é
sempre st.session_state.cronograma na UI — nunca reconstruído via
listar_tarefas_por_projeto(), que descarta as linhas-resumo (ver
infra/repositorio.py::salvar_cronograma).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pmo_assistant.core.models import Cronograma, TarefaCronograma

_PCT_COMPLETO = 100.0


def tarefa_raiz(cr: Cronograma) -> TarefaCronograma | None:
    """Linha-resumo do projeto (id_tarefa == 1). Contém os agregados gerais
    (percentual esperado geral, baselines, término com impacto) que não
    existem em nenhuma tarefa de folha. Pode ser None se o PDF não tiver
    linha-resumo raiz; chamador deve tratar com fallback gracioso.
    """
    return next((t for t in cr.tarefas if t.id_tarefa == 1), None)


def classificar_tarefas_por_status(tarefas: list[TarefaCronograma]) -> dict[str, int]:
    """Classifica tarefas de folha (eh_resumo=False) em 4 categorias.

    Concluída: percentual_concluido >= 100 (implica atrasada=False, ver
        TarefaCronograma.atrasada — uma tarefa 100% nunca é marcada atrasada).
    Atrasada: atrasada is True (usa o computed_field já existente — não
        reimplemente a lógica de atraso aqui).
    Tarefa Futura: ainda não iniciada (inicio_real is None) e não atrasada.
    No Prazo: tudo o mais — em andamento, dentro do previsto.
    """
    folhas = [t for t in tarefas if not t.eh_resumo]
    contagem = {"Concluída": 0, "No Prazo": 0, "Atrasada": 0, "Tarefa Futura": 0}
    for t in folhas:
        if t.percentual_concluido >= _PCT_COMPLETO:
            contagem["Concluída"] += 1
        elif t.atrasada:
            contagem["Atrasada"] += 1
        elif t.inicio_real is None:
            contagem["Tarefa Futura"] += 1
        else:
            contagem["No Prazo"] += 1
    return contagem


def atividades_realizadas(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [t for t in tarefas if not t.eh_resumo and t.percentual_concluido >= _PCT_COMPLETO]


def proximas_atividades(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [
        t
        for t in tarefas
        if not t.eh_resumo and t.percentual_concluido < _PCT_COMPLETO and not t.atrasada
    ]


def pontos_de_atencao(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [t for t in tarefas if not t.eh_resumo and t.atrasada]


def texto_cronograma_para_fts(cr: Cronograma) -> str:
    """Serializa o cronograma como texto pesquisável pelo FTS5 (infra/busca.py).

    Sem isso, o chat (objetivo 3) nunca vê dados de cronograma — só de atas.
    Preserva termos que o usuário usará em perguntas ("atrasada", "concluída",
    datas em pt-BR). Linhas-resumo (eh_resumo=True) são excluídas: são agregados
    de fase, não atividades que o usuário pergunta por nome.
    """
    linhas = [f"Cronograma do projeto: {cr.nome_projeto}"]
    if cr.data_referencia:
        linhas.append(f"Data de referência: {cr.data_referencia.strftime('%d/%m/%Y')}")

    for t in cr.tarefas:
        if t.eh_resumo:
            continue
        if t.percentual_concluido >= _PCT_COMPLETO:
            status = "concluída"
        elif t.atrasada:
            status = "atrasada"
        elif t.inicio_real is None:
            status = "futura"
        else:
            status = "em andamento"

        partes = [
            f"Atividade: {t.nome}. Status: {status}.",
            f"Percentual concluído: {t.percentual_concluido:.0f}%.",
        ]
        if t.termino_baseline:
            partes.append(f"Previsão original: {t.termino_baseline.strftime('%d/%m/%Y')}.")
        if t.inicio:
            partes.append(f"Início previsto: {t.inicio.strftime('%d/%m/%Y')}.")
        if t.termino:
            partes.append(f"Término previsto: {t.termino.strftime('%d/%m/%Y')}.")
        if t.termino_real:
            partes.append(f"Concluída em: {t.termino_real.strftime('%d/%m/%Y')}.")
        linhas.append(" ".join(partes))

    return "\n".join(linhas)
