"""Busca full-text sobre documentos via SQLite FTS5. Sem embeddings, sem chamada de API.

Substitui o índice semântico originalmente planejado (embeddings via Anthropic SDK —
inexistente; ver CLAUDE.md). BM25 do FTS5 nativo do SQLite serve de ranking. A tabela
virtual `documentos_fts` é criada via migration Alembic (ver alembic/versions/*add_conteudo_bruto*).
"""

from __future__ import annotations

import re
from typing import Any

from sqlalchemy import Engine, text

_MIN_CHARS_CHUNK = 50


def chunkar(texto: str, max_chars: int = 800, sobreposicao_paragrafos: int = 1) -> list[str]:
    """Divide texto em chunks por parágrafo, com sobreposição para preservar contexto.

    Agrupa parágrafos consecutivos até `max_chars`; cada chunk novo reinicia incluindo
    os últimos `sobreposicao_paragrafos` parágrafos do chunk anterior. Chunks curtos
    demais (ruído de formatação) são descartados.
    """
    paragrafos = [p.strip() for p in re.split(r"\n\s*\n|\n", texto) if p.strip()]
    if not paragrafos:
        return []

    chunks: list[str] = []
    atual: list[str] = []
    atual_len = 0

    for paragrafo in paragrafos:
        if atual and atual_len + len(paragrafo) + 1 > max_chars:
            chunks.append("\n".join(atual))
            atual = atual[-sobreposicao_paragrafos:] if sobreposicao_paragrafos > 0 else []
            atual_len = sum(len(p) + 1 for p in atual)
        atual.append(paragrafo)
        atual_len += len(paragrafo) + 1

    if atual:
        chunks.append("\n".join(atual))

    return [c for c in chunks if len(c) >= _MIN_CHARS_CHUNK]


def reindexar_documento(engine: Engine, documento_id: int, projeto_id: int, texto: str) -> None:
    """(Re)indexa um documento no FTS5. Idempotente: apaga chunks antigos antes de inserir."""
    chunks = chunkar(texto)
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM documentos_fts WHERE documento_id = :documento_id"),
            {"documento_id": documento_id},
        )
        if chunks:
            conn.execute(
                text(
                    "INSERT INTO documentos_fts (chunk_texto, documento_id, projeto_id) "
                    "VALUES (:chunk_texto, :documento_id, :projeto_id)"
                ),
                [
                    {"chunk_texto": c, "documento_id": documento_id, "projeto_id": projeto_id}
                    for c in chunks
                ],
            )


def _sanitizar_consulta(consulta: str) -> str:
    """Monta uma expressão MATCH segura a partir de texto livre do usuário.

    Tokeniza por palavra e une com OR — evita erro de sintaxe do FTS5 quando o texto
    contém caracteres especiais da linguagem de query (aspas, hífen, etc.).
    """
    termos = re.findall(r"\w+", consulta.lower())
    return " OR ".join(f'"{t}"' for t in termos)


def buscar(
    engine: Engine, consulta: str, k: int = 5, projeto_id: int | None = None
) -> list[dict[str, Any]]:
    """Busca os k trechos mais relevantes via BM25 do FTS5.

    `rank` é o score bruto do bm25() — negativo, quanto menor (mais negativo) mais
    relevante. Lista vazia significa nenhum chunk bateu no MATCH.
    """
    query_fts = _sanitizar_consulta(consulta)
    if not query_fts:
        return []

    sql = (
        "SELECT chunk_texto, documento_id, projeto_id, bm25(documentos_fts) AS rank "
        "FROM documentos_fts WHERE documentos_fts MATCH :consulta"
    )
    params: dict[str, Any] = {"consulta": query_fts, "k": k}
    if projeto_id is not None:
        sql += " AND projeto_id = :projeto_id"
        params["projeto_id"] = projeto_id
    sql += " ORDER BY rank LIMIT :k"

    with engine.connect() as conn:
        linhas = conn.execute(text(sql), params).mappings().all()

    return [
        {
            "texto": linha["chunk_texto"],
            "documento_id": linha["documento_id"],
            "projeto_id": linha["projeto_id"],
            "rank": linha["rank"],
        }
        for linha in linhas
    ]
