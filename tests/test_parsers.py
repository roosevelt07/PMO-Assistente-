"""Testes do parser de cronograma. Usa linhas reais (anonimizadas) dos dois layouts."""

from __future__ import annotations

from datetime import date

from pmo_assistant.core.parsers.cronograma import parsear_cronograma

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
