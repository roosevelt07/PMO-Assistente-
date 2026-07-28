"""Testes do parser de cronograma. Usa linhas reais (anonimizadas) dos dois layouts."""

from __future__ import annotations

from datetime import date, timedelta

from pmo_assistant.core.parsers.cronograma import detectar_layout, parsear_cronograma

# Trecho real do layout Charqueadas (com baseline e % esperado)
CHARQUEADAS = """\
Id Modo da Tarefa Nome da Tarefa % concluída % Expected
1 173.03 GRANTEL-AXIA SUL-AMPL SE CHARQUEADAS (TLC)94% 99% Qua 03/12/25Qui 09/07/26Qua 03/12/25Ter 11/08/26Qua 03/12/25ND
2 INICIALIZAÇÃO 100% 100% Qua 03/12/25Qua 03/12/25Qua 03/12/25Qua 03/12/25Qua 03/12/25Qua 03/12/25
78 Aguardar a aprovação do Diagrama de Arquitetura 32% 100% Qua 18/03/26Qui 26/03/26Seg 13/04/26Ter 02/06/26Seg 13/04/26ND
Data: Qua 03/06/26
"""

# Trecho real do layout Atiaia (simples, sem baseline)
ATIAIA = """\
Id Modo da Tarefa Nome da Tarefa % concluída Início Término
1 L2 ENGENHARIA-ATIAIA - SE BARRA DE COQUEIROS (CFTV) 5% Qui 05/02/26 Ter 18/08/26
7 Elaborar e emitir o Workstatement de CFTV 100% Ter 12/05/26 Seg 18/05/26
11 Elaborar e emitir o Workstatement de Detecção de Incêndio100% Ter 12/05/26 Seg 18/05/26
Data: Ter 02/06/26
"""


def test_parser_charqueadas_baseline():
    cr = parsear_cronograma(CHARQUEADAS, projeto_id=1, nome_projeto="Charqueadas")
    assert cr.data_referencia == date(2026, 6, 3)
    assert cr.percentual_geral == 94.0
    raiz = next(t for t in cr.tarefas if t.id_tarefa == 1)
    assert raiz.percentual_esperado == 99.0
    assert raiz.termino == date(2026, 8, 11)
    assert raiz.termino_baseline == date(2026, 7, 9)
    assert raiz.atrasada  # término real estourou baseline
    # tarefa 78: 32% concluído vs 100% esperado -> atrasada
    t78 = next(t for t in cr.tarefas if t.id_tarefa == 78)
    assert t78.atrasada


def test_parser_atiaia_simples():
    cr = parsear_cronograma(ATIAIA, projeto_id=2, nome_projeto="Atiaia")
    assert cr.data_referencia == date(2026, 6, 2)
    assert cr.percentual_geral == 5.0
    # sem baseline, nenhuma tarefa marcada atrasada
    assert cr.total_atrasadas == 0
    t7 = next(t for t in cr.tarefas if t.id_tarefa == 7)
    assert t7.percentual_concluido == 100.0
    assert t7.percentual_esperado is None
    # nome colado ao % é separado corretamente
    t11 = next(t for t in cr.tarefas if t.id_tarefa == 11)
    assert "Incêndio" in t11.nome
    assert t11.percentual_concluido == 100.0


def test_parser_ignora_paginas_gantt():
    # linhas sem % (cabeçalho de gantt) não viram tarefas
    gantt = "N D J F MAM J J A S ON\nSemestre 2 2026 Semestre 1 2027\n"
    cr = parsear_cronograma(gantt, projeto_id=3, nome_projeto="X")
    assert len(cr.tarefas) == 0


# Layout B — Dashboard Executivo (Tripla, Usina Santo Antônio): sem baseline,
# IDs decimais (1.1, 2.1), status literal em vez de %.
DASHBOARD_MINIMO = """\
Dashboard Executivo — Projeto Tripla
ID Resp. Início Prev. Conclusão Prev. Status % Execução
1.1 João Elaborar diagrama de arquitetura 01/01/26 10/03/26 Concluído 100%
1.2 Maria Instalar equipamento de campo 05/02/26 20/09/26 Em Andamento 40%
Resumo
Concluído 30 73%
Total Geral 41 100%
A Iniciar 11
"""


def test_detectar_layout_ms_project():
    assert detectar_layout(CHARQUEADAS) == "ms_project"


def test_detectar_layout_dashboard():
    assert detectar_layout(DASHBOARD_MINIMO) == "dashboard_executivo"


def test_detectar_layout_desconhecido():
    assert detectar_layout("texto qualquer sem relação com cronograma") == "desconhecido"


def test_parsear_cronograma_vazio_avisa():
    # layout desconhecido cai no fallback MS Project, que não acha nada -> vazio, sem exceção
    cr = parsear_cronograma("texto qualquer sem relação", projeto_id=4, nome_projeto="Y")
    assert cr.tarefas == []


def test_parsear_dashboard_executivo_basico():
    cr = parsear_cronograma(DASHBOARD_MINIMO, projeto_id=5, nome_projeto="Tripla")
    assert len(cr.tarefas) == 3  # 1 resumo sintético + 2 tarefas reais

    raiz = next(t for t in cr.tarefas if t.id_tarefa == 1)
    assert raiz.eh_resumo
    assert raiz.percentual_concluido == 73.0
    assert raiz.percentual_esperado is None
    assert cr.percentual_geral == 73.0

    t1 = next(t for t in cr.tarefas if "diagrama de arquitetura" in t.nome)
    assert t1.percentual_concluido == 100.0
    assert t1.percentual_esperado is None
    assert t1.inicio == date(2026, 1, 1)
    assert t1.termino == date(2026, 3, 10)
    assert not t1.eh_resumo

    t2 = next(t for t in cr.tarefas if "equipamento de campo" in t.nome)
    assert t2.percentual_concluido == 50.0  # "Em Andamento" -> 50%
    assert t2.inicio_real == date(2026, 2, 5)
    assert t2.termino_real is None  # ainda não concluída


def test_parsear_dashboard_executivo_marca_atrasada():
    ontem = (date.today() - timedelta(days=1)).strftime("%d/%m/%y")
    texto = f"""\
ID Resp. Início Prev. Conclusão Prev. Status % Execução
2.1 Pedro Homologar sistema de proteção 01/01/26 {ontem} A Iniciar 0%
Concluído 0 0%
Total Geral 1 0%
A Iniciar 1
"""
    cr = parsear_cronograma(texto, projeto_id=6, nome_projeto="Z")
    tarefa = next(t for t in cr.tarefas if not t.eh_resumo)
    assert tarefa.termino is not None and tarefa.termino < date.today()
    assert tarefa.percentual_concluido < 100.0
    assert tarefa.atrasada
