"""Cliente LLM Anthropic: tool use estruturado, cache em disco, retry com jitter.

Implementa o Protocol LLMClient de core/extractors/acoes.py.
"""

from __future__ import annotations

import os
import random
import time
from typing import TYPE_CHECKING, Any

import anthropic
from anthropic.types import ToolUseBlock
from loguru import logger

from pmo_assistant.infra.cache import CacheLLM

if TYPE_CHECKING:
    from pydantic import BaseModel

MODELO_PADRAO = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_TENTATIVAS = 4


def _get_api_key() -> str:
    """Streamlit Cloud injeta via st.secrets; local usa .env."""
    try:
        import streamlit as st  # noqa: PLC0415 — evita import circular fora de contexto Streamlit

        return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:
        key = os.getenv("ANTHROPIC_API_KEY", "")
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY não configurada. "
                "Defina em .env (local) ou Secrets (Streamlit Cloud)."
            ) from None
        return key


class LLMClient:
    """Cliente Anthropic com tool use forçado."""

    def __init__(
        self,
        api_key: str | None = None,
        modelo: str = MODELO_PADRAO,
        cache: CacheLLM | None = None,
    ) -> None:
        key = api_key or _get_api_key()
        self._client = anthropic.Anthropic(api_key=key)
        self._modelo = modelo
        self._cache = cache or CacheLLM()

    def extrair_estruturado(
        self, system: str, user: str, schema: type[BaseModel], nome_ferramenta: str
    ) -> dict[str, Any]:
        """Força o modelo a chamar uma tool com schema derivado do Pydantic.

        Retorna o input da tool_use, pronto para schema.model_validate().
        """
        tool = {
            "name": nome_ferramenta,
            "description": schema.__doc__ or f"Registra dados ({nome_ferramenta})",
            "input_schema": schema.model_json_schema(),
        }
        chave = self._cache.chave(system, user, self._modelo, nome_ferramenta)
        if (cached := self._cache.obter(chave)) is not None:
            logger.debug("cache hit LLM | {}", chave[:12])
            return cached

        ultima_exc: Exception | None = None
        for tentativa in range(1, MAX_TENTATIVAS + 1):
            try:
                resp = self._client.messages.create(
                    model=self._modelo,
                    max_tokens=MAX_TOKENS,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                    tools=[tool],
                    tool_choice={"type": "tool", "name": nome_ferramenta},
                )
                if resp.stop_reason != "tool_use":
                    raise RuntimeError(f"stop_reason={resp.stop_reason}, esperado tool_use")
                for bloco in resp.content:
                    if isinstance(bloco, ToolUseBlock) and bloco.name == nome_ferramenta:
                        payload = dict(bloco.input) if isinstance(bloco.input, dict) else {}
                        self._cache.gravar(chave, payload)
                        logger.info(
                            "extração ok | tent={} in={} out={}",
                            tentativa, resp.usage.input_tokens, resp.usage.output_tokens,
                        )
                        return payload
                raise RuntimeError("resposta sem bloco tool_use correspondente")
            except (anthropic.APIStatusError, anthropic.APIConnectionError) as exc:
                ultima_exc = exc
                espera = min(60.0, 2**tentativa) + random.uniform(0, 1)  # backoff + jitter
                logger.warning(
                    "falha LLM tent={}/{} {} espera={:.1f}s",
                    tentativa, MAX_TENTATIVAS, type(exc).__name__, espera,
                )
                time.sleep(espera)
        raise RuntimeError(f"falha após {MAX_TENTATIVAS} tentativas: {ultima_exc}") from ultima_exc
