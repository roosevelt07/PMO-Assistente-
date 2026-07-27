"""Cache em disco de respostas LLM. Obrigatório em desenvolvimento.

Chave: SHA-256 de (modelo|ferramenta|system|user). Valor: JSON do payload.
Limpar tudo: rm -rf data/cache/llm/
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from loguru import logger

DEFAULT_DIR = Path("data/cache/llm")


class CacheLLM:
    def __init__(self, diretorio: Path | None = None) -> None:
        self._dir = diretorio or DEFAULT_DIR
        self._dir.mkdir(parents=True, exist_ok=True)

    def chave(self, system: str, user: str, modelo: str, ferramenta: str) -> str:
        material = f"{modelo}|{ferramenta}|{system}|{user}".encode()
        return hashlib.sha256(material).hexdigest()

    def obter(self, chave: str) -> dict[str, Any] | None:
        caminho = self._dir / f"{chave}.json"
        if not caminho.exists():
            return None
        try:
            with caminho.open(encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("cache corrompido {} ({})", caminho, exc)
            return None

    def gravar(self, chave: str, payload: dict[str, Any]) -> None:
        caminho = self._dir / f"{chave}.json"
        try:
            with caminho.open("w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except OSError as exc:
            logger.warning("falha ao gravar cache {}: {}", caminho, exc)
