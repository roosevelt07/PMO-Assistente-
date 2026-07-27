"""CLI auxiliar.

uv run python -m pmo_assistant.cli init-db
uv run python -m pmo_assistant.cli limpar-cache
"""

from __future__ import annotations

import shutil
from pathlib import Path

import typer
from loguru import logger

from pmo_assistant.infra.cache import DEFAULT_DIR as CACHE_DIR
from pmo_assistant.infra.db import criar_engine, inicializar_schema

app = typer.Typer(help="PMO Assistant — utilitários")


@app.command("init-db")
def init_db(caminho: Path | None = None) -> None:
    """Cria as tabelas (dev; produção usa Alembic)."""
    inicializar_schema(criar_engine(caminho))
    logger.info("schema inicializado")


@app.command("limpar-cache")
def limpar_cache() -> None:
    """Apaga o cache de respostas LLM."""
    if CACHE_DIR.exists():
        shutil.rmtree(CACHE_DIR)
        logger.info("cache removido: {}", CACHE_DIR)
    else:
        logger.info("cache vazio")


if __name__ == "__main__":
    app()
