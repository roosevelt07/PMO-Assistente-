"""Testes de infra/busca.py: chunking + índice FTS5. Sem chamada de API."""

from __future__ import annotations

import pytest
from sqlalchemy import Engine, create_engine, text

from pmo_assistant.infra.busca import buscar, chunkar, reindexar_documento


@pytest.fixture
def engine_fts() -> Engine:
    eng = create_engine("sqlite://")
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE VIRTUAL TABLE documentos_fts USING fts5(
                    chunk_texto,
                    documento_id UNINDEXED,
                    projeto_id UNINDEXED,
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )
        )
    return eng


def test_chunkar_agrupa_paragrafos_ate_max_chars() -> None:
    texto = (
        "Primeiro parágrafo com conteúdo suficiente para não ser descartado.\n\n"
        "Segundo parágrafo também com bastante texto útil."
    )
    chunks = chunkar(texto, max_chars=1000)
    assert len(chunks) == 1
    assert "Primeiro parágrafo" in chunks[0]
    assert "Segundo parágrafo" in chunks[0]


def test_chunkar_descarta_chunk_curto_demais() -> None:
    assert chunkar("curto", max_chars=800) == []


def test_chunkar_respeita_max_chars_com_sobreposicao() -> None:
    paragrafos = [f"Parágrafo número {i} com texto o bastante para contar." for i in range(6)]
    texto = "\n\n".join(paragrafos)
    chunks = chunkar(texto, max_chars=120, sobreposicao_paragrafos=1)
    assert len(chunks) > 1
    # o último parágrafo de um chunk reaparece no início do próximo (sobreposição)
    assert chunks[0].splitlines()[-1] in chunks[1]


def test_chunkar_sobreposicao_zero_nao_repete_paragrafo() -> None:
    paragrafos = [f"Parágrafo número {i} com texto o bastante para contar." for i in range(6)]
    texto = "\n\n".join(paragrafos)
    chunks = chunkar(texto, max_chars=120, sobreposicao_paragrafos=0)
    assert len(chunks) > 1
    assert chunks[0].splitlines()[-1] not in chunks[1]


def test_chunkar_texto_vazio() -> None:
    assert chunkar("") == []
    assert chunkar("   \n\n  ") == []


def test_reindexar_e_buscar_encontra_trecho_relevante(engine_fts: Engine) -> None:
    texto = (
        "A NETCON ficou responsável por enviar o cronograma executivo até 03/12.\n\n"
        "O escopo do projeto Charqueadas inclui substituição de transformadores."
    )
    reindexar_documento(engine_fts, documento_id=1, projeto_id=10, texto=texto)

    resultados = buscar(engine_fts, "cronograma executivo NETCON", k=5)
    assert len(resultados) >= 1
    assert "NETCON" in resultados[0]["texto"]
    assert resultados[0]["documento_id"] == 1


def test_buscar_filtra_por_projeto(engine_fts: Engine) -> None:
    reindexar_documento(engine_fts, documento_id=1, projeto_id=10, texto="A" * 60)
    reindexar_documento(engine_fts, documento_id=2, projeto_id=20, texto="A" * 60)

    resultados = buscar(engine_fts, "aaaaa", k=10, projeto_id=10)
    assert all(r["projeto_id"] == 10 for r in resultados)


def test_buscar_sem_resultado_retorna_lista_vazia(engine_fts: Engine) -> None:
    reindexar_documento(engine_fts, documento_id=1, projeto_id=10, texto="conteúdo qualquer sobre engenharia elétrica")
    assert buscar(engine_fts, "xenoblade termos que não existem em lugar nenhum") == []


def test_reindexar_documento_e_idempotente(engine_fts: Engine) -> None:
    texto = "Conteúdo original do documento sobre o projeto Barra dos Coqueiros."
    reindexar_documento(engine_fts, documento_id=1, projeto_id=10, texto=texto)
    reindexar_documento(engine_fts, documento_id=1, projeto_id=10, texto=texto)

    resultados = buscar(engine_fts, "Barra Coqueiros", k=10)
    assert len(resultados) == 1
