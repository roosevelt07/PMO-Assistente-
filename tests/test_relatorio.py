"""Testes de core/relatorio.py — agregação pura para status report."""

from __future__ import annotations

from datetime import date

from pmo_assistant.core.models import Cronograma, TarefaCronograma
from pmo_assistant.core.relatorio import (
    atividades_realizadas,
    classificar_tarefas_por_status,
    pontos_de_atencao,
    proximas_atividades,
    tarefa_raiz,
)


def test_tarefa_raiz_encontra_id_1():
    cr = Cronograma(
        projeto_id=1,
        nome_projeto="P",
        tarefas=[
            TarefaCronograma(id_tarefa=2, nome="Sub", percentual_concluido=50.0),
            TarefaCronograma(id_tarefa=1, nome="P", percentual_concluido=90.0, eh_resumo=True),
        ],
    )
    raiz = tarefa_raiz(cr)
    assert raiz is not None
    assert raiz.id_tarefa == 1


def test_tarefa_raiz_none_se_ausente():
    cr = Cronograma(
        projeto_id=1,
        nome_projeto="P",
        tarefas=[TarefaCronograma(id_tarefa=2, nome="Sub", percentual_concluido=50.0)],
    )
    assert tarefa_raiz(cr) is None


def test_classificar_quatro_categorias_e_ignora_resumo():
    tarefas = [
        TarefaCronograma(
            id_tarefa=1,
            nome="Resumo",
            percentual_concluido=10.0,
            percentual_esperado=90.0,
            eh_resumo=True,
        ),
        TarefaCronograma(id_tarefa=2, nome="Concluída", percentual_concluido=100.0),
        TarefaCronograma(
            id_tarefa=3, nome="Atrasada", percentual_concluido=40.0, percentual_esperado=60.0
        ),
        TarefaCronograma(id_tarefa=4, nome="Futura", percentual_concluido=0.0),
        TarefaCronograma(
            id_tarefa=5,
            nome="No Prazo",
            percentual_concluido=50.0,
            inicio_real=date(2026, 1, 1),
        ),
    ]
    contagem = classificar_tarefas_por_status(tarefas)
    assert contagem == {"Concluída": 1, "No Prazo": 1, "Atrasada": 1, "Tarefa Futura": 1}


def test_classificar_lista_vazia():
    assert classificar_tarefas_por_status([]) == {
        "Concluída": 0,
        "No Prazo": 0,
        "Atrasada": 0,
        "Tarefa Futura": 0,
    }


def test_atividades_realizadas_filtra_concluidas_e_ignora_resumo():
    tarefas = [
        TarefaCronograma(
            id_tarefa=1, nome="Resumo", percentual_concluido=100.0, eh_resumo=True
        ),
        TarefaCronograma(
            id_tarefa=2, nome="Feita", percentual_concluido=100.0, termino_real=date(2026, 6, 1)
        ),
        TarefaCronograma(id_tarefa=3, nome="Em andamento", percentual_concluido=50.0),
    ]
    resultado = atividades_realizadas(tarefas)
    assert [t.id_tarefa for t in resultado] == [2]


def test_atividades_realizadas_lista_vazia():
    assert atividades_realizadas([]) == []


def test_proximas_atividades_filtra_em_andamento_nao_atrasadas():
    tarefas = [
        TarefaCronograma(id_tarefa=2, nome="Pendente", percentual_concluido=30.0),
        TarefaCronograma(
            id_tarefa=3, nome="Atrasada", percentual_concluido=30.0, percentual_esperado=80.0
        ),
        TarefaCronograma(id_tarefa=4, nome="Concluída", percentual_concluido=100.0),
    ]
    resultado = proximas_atividades(tarefas)
    assert [t.id_tarefa for t in resultado] == [2]


def test_proximas_atividades_lista_vazia():
    assert proximas_atividades([]) == []


def test_pontos_de_atencao_filtra_atrasadas():
    tarefas = [
        TarefaCronograma(id_tarefa=2, nome="No prazo", percentual_concluido=50.0),
        TarefaCronograma(
            id_tarefa=3, nome="Atrasada", percentual_concluido=30.0, percentual_esperado=80.0
        ),
        TarefaCronograma(
            id_tarefa=1,
            nome="Resumo atrasado",
            percentual_concluido=10.0,
            percentual_esperado=90.0,
            eh_resumo=True,
        ),
    ]
    resultado = pontos_de_atencao(tarefas)
    assert [t.id_tarefa for t in resultado] == [3]


def test_pontos_de_atencao_lista_vazia():
    assert pontos_de_atencao([]) == []
