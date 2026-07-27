"""Avaliação de saúde do projeto: cruza cronograma + ações pendentes.

Lógica pura e determinística. Sem LLM, sem I/O.
Implementa o objetivo 3 do TCC: apoio à decisão.
"""

from __future__ import annotations

from pmo_assistant.core.models import (
    Cronograma,
    NivelSaude,
    SaudeProjeto,
    StatusAcao,
)

# limiares de desvio (pontos percentuais) entre concluído real e esperado
_LIMIAR_RISCO = 5.0
_LIMIAR_ATRASO = 15.0


def avaliar_saude(
    cronograma: Cronograma,
    acoes_status: list[StatusAcao] | None = None,
) -> SaudeProjeto:
    """Deriva o nível de saúde a partir do cronograma e das ações.

    Regra:
    - desvio = %esperado - %concluído (na linha-resumo do projeto, id=1)
    - desvio >= 15pp OU término impactado > baseline -> ATRASADO
    - desvio >= 5pp OU existe tarefa atrasada -> EM_RISCO
    - caso contrário -> NO_PRAZO
    Ações pendentes entram como agravante e na justificativa.
    """
    acoes_status = acoes_status or []
    pendentes = sum(
        1
        for s in acoes_status
        if s in (StatusAcao.NAO_INICIADA, StatusAcao.EM_ANDAMENTO, StatusAcao.ATRASADA)
    )

    raiz = next((t for t in cronograma.tarefas if t.id_tarefa == 1), None)
    if raiz is None:
        return SaudeProjeto(
            projeto_id=cronograma.projeto_id,
            nome_projeto=cronograma.nome_projeto,
            nivel=NivelSaude.SEM_DADOS,
            acoes_pendentes=pendentes,
            justificativa="Cronograma sem linha-resumo do projeto (id=1).",
        )

    pct_real = raiz.percentual_concluido
    pct_esp = raiz.percentual_esperado
    desvio = (pct_esp - pct_real) if pct_esp is not None else 0.0
    impacto_baseline = (
        raiz.termino is not None
        and raiz.termino_baseline is not None
        and raiz.termino > raiz.termino_baseline
    )

    if desvio >= _LIMIAR_ATRASO or impacto_baseline:
        nivel = NivelSaude.ATRASADO
    elif desvio >= _LIMIAR_RISCO or cronograma.total_atrasadas > 0:
        nivel = NivelSaude.EM_RISCO
    else:
        nivel = NivelSaude.NO_PRAZO

    partes = []
    if pct_esp is not None:
        partes.append(
            f"{pct_real:.0f}% concluído vs {pct_esp:.0f}% esperado (desvio {desvio:.0f}pp)"
        )
    else:
        partes.append(f"{pct_real:.0f}% concluído")
    if cronograma.total_atrasadas:
        partes.append(f"{cronograma.total_atrasadas} tarefas atrasadas")
    if impacto_baseline:
        partes.append(f"término impactado de {raiz.termino_baseline} para {raiz.termino}")
    if pendentes:
        partes.append(f"{pendentes} ações pendentes")

    return SaudeProjeto(
        projeto_id=cronograma.projeto_id,
        nome_projeto=cronograma.nome_projeto,
        nivel=nivel,
        percentual_concluido=pct_real,
        percentual_esperado=pct_esp,
        tarefas_atrasadas=cronograma.total_atrasadas,
        acoes_pendentes=pendentes,
        justificativa="; ".join(partes) + ".",
    )
