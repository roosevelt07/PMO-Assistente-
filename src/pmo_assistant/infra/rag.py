"""RAG via ChromaDB embedded + sentence-transformers (embeddings locais, sem custo).

Singleton de cliente para evitar travamento por múltiplas conexões.
"""

from __future__ import annotations

from pathlib import Path
from threading import Lock
from typing import Any

import chromadb
from chromadb.config import Settings
from chromadb.utils import embedding_functions
from loguru import logger

DEFAULT_DIR = Path("data/chroma")
COLECAO_PADRAO = "documentos"
MODELO_EMBEDDINGS = "paraphrase-multilingual-MiniLM-L12-v2"

_cliente: chromadb.ClientAPI | None = None
_lock = Lock()


def _get_cliente(diretorio: Path = DEFAULT_DIR) -> chromadb.ClientAPI:
    global _cliente
    with _lock:
        if _cliente is None:
            diretorio.mkdir(parents=True, exist_ok=True)
            _cliente = chromadb.PersistentClient(
                path=str(diretorio), settings=Settings(anonymized_telemetry=False)
            )
            logger.info("ChromaDB inicializado em {}", diretorio)
        return _cliente


class RAGIndex:
    """Coleção ChromaDB para indexar e buscar trechos de documentos."""

    def __init__(self, nome_colecao: str = COLECAO_PADRAO) -> None:
        cliente = _get_cliente()
        embed = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=MODELO_EMBEDDINGS
        )
        self._colecao = cliente.get_or_create_collection(
            name=nome_colecao, embedding_function=embed, metadata={"hnsw:space": "cosine"}
        )

    def indexar(
        self, documento_id: int, trechos: list[str], metadata_extra: dict[str, Any] | None = None
    ) -> None:
        if not trechos:
            return
        ids = [f"doc-{documento_id}-{i}" for i in range(len(trechos))]
        metas = [
            {"documento_id": documento_id, "indice": i, **(metadata_extra or {})}
            for i in range(len(trechos))
        ]
        self._colecao.add(ids=ids, documents=trechos, metadatas=metas)
        logger.info("indexados {} trechos | doc={}", len(trechos), documento_id)

    def buscar(self, consulta: str, k: int = 5) -> list[dict[str, Any]]:
        res = self._colecao.query(query_texts=[consulta], n_results=k)
        docs = res.get("documents", [[]])[0]
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        return [
            {"texto": d, "metadata": m, "distancia": dist}
            for d, m, dist in zip(docs, metas, dists, strict=False)
        ]
