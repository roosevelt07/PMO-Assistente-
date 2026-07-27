"""Testes de round-trip do repositório contra um SQLite em memória."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest
from sqlalchemy.orm import Session

from pmo_assistant.core.models import AcaoExtraida, StatusAcao, TarefaCronograma, TipoDocumento
from pmo_assistant.infra.db import criar_engine, inicializar_schema
from pmo_assistant.infra.repositorio import (
    listar_acoes_por_projeto,
    listar_projetos,
    listar_tarefas_por_projeto,
    salvar_cronograma,
    salvar_documento_com_acoes,
    salvar_projeto,
)


@pytest.fixture
def session():
    engine = criar_engine(Path(":memory:"))
    inicializar_schema(engine)
    with Session(engine) as sess:
        yield sess


def test_salvar_projeto_round_trip(session):
    projeto = salvar_projeto(session, nome="Charqueadas TLC", cliente="Netcon")

    assert projeto.id is not None
    projetos = listar_projetos(session)
    assert len(projetos) == 1
    assert projetos[0].nome == "Charqueadas TLC"
    assert projetos[0].cliente == "Netcon"


def test_salvar_documento_com_acoes_round_trip(session):
    projeto = salvar_projeto(session, nome="Barra dos Coqueiros CFTV")
    acoes = [
        AcaoExtraida(
            descricao="Enviar cronograma executivo do projeto",
            responsavel="NETCON",
            prazo=date(2025, 12, 3),
            status=StatusAcao.NAO_INICIADA,
            contexto_origem="Netcon informou que enviará o cronograma executivo.",
            confianca=0.9,
        ),
        AcaoExtraida(
            descricao="Revisar contrato com fornecedor",
            contexto_origem="Sem responsável identificado na ata.",
            confianca=0.4,
        ),
    ]

    documento = salvar_documento_com_acoes(
        session,
        projeto_id=projeto.id,
        nome_arquivo="ata_kickoff.pdf",
        tipo=TipoDocumento.KICKOFF,
        resumo="Ata de KickOff do projeto.",
        acoes=acoes,
    )

    assert documento.id is not None
    assert documento.tipo == "kickoff"

    salvas = listar_acoes_por_projeto(session, projeto.id)
    assert len(salvas) == 2
    salvas_por_descricao = {a.descricao: a for a in salvas}
    a1 = salvas_por_descricao["Enviar cronograma executivo do projeto"]
    assert a1.responsavel == "NETCON"
    assert a1.prazo == date(2025, 12, 3)
    assert a1.status == StatusAcao.NAO_INICIADA.value
    assert a1.documento.nome_arquivo == "ata_kickoff.pdf"

    a2 = salvas_por_descricao["Revisar contrato com fornecedor"]
    assert a2.responsavel is None


def test_listar_acoes_por_projeto_isola_por_projeto(session):
    p1 = salvar_projeto(session, nome="Projeto 1")
    p2 = salvar_projeto(session, nome="Projeto 2")
    acao = AcaoExtraida(
        descricao="Ação exclusiva do projeto 1",
        contexto_origem="trecho",
        confianca=0.8,
    )
    salvar_documento_com_acoes(
        session, p1.id, "doc1.pdf", TipoDocumento.STATUS_REPORT, "resumo", [acao]
    )

    assert len(listar_acoes_por_projeto(session, p1.id)) == 1
    assert len(listar_acoes_por_projeto(session, p2.id)) == 0


def test_salvar_cronograma_ignora_linhas_resumo(session):
    projeto = salvar_projeto(session, nome="Charqueadas TLC")
    tarefas = [
        TarefaCronograma(
            id_tarefa=1, nome="PLANEJAMENTO", percentual_concluido=50.0,
            percentual_esperado=80.0, eh_resumo=True,
        ),
        TarefaCronograma(
            id_tarefa=2, nome="Elaborar projeto executivo", percentual_concluido=70.0,
            percentual_esperado=95.0,
            termino=date(2026, 8, 11), termino_baseline=date(2026, 7, 9),
        ),
        TarefaCronograma(
            id_tarefa=3, nome="Solicitar licença ambiental", percentual_concluido=100.0,
            percentual_esperado=100.0,
        ),
    ]

    salvas = salvar_cronograma(session, projeto.id, tarefas)

    assert len(salvas) == 2  # linha-resumo (id_tarefa=1) foi ignorada
    do_banco = listar_tarefas_por_projeto(session, projeto.id)
    assert len(do_banco) == 2
    nomes = {t.nome for t in do_banco}
    assert nomes == {"Elaborar projeto executivo", "Solicitar licença ambiental"}

    atrasada = next(t for t in do_banco if t.nome == "Elaborar projeto executivo")
    assert atrasada.atrasada is True
    no_prazo = next(t for t in do_banco if t.nome == "Solicitar licença ambiental")
    assert no_prazo.atrasada is False


def test_listar_tarefas_por_projeto_isola_por_projeto(session):
    p1 = salvar_projeto(session, nome="Projeto 1")
    p2 = salvar_projeto(session, nome="Projeto 2")
    salvar_cronograma(
        session, p1.id,
        [TarefaCronograma(id_tarefa=1, nome="Tarefa única", percentual_concluido=10.0)],
    )

    assert len(listar_tarefas_por_projeto(session, p1.id)) == 1
    assert len(listar_tarefas_por_projeto(session, p2.id)) == 0
