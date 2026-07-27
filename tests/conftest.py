"""Fixtures de teste."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from pydantic import BaseModel


class FakeLLMClient:
    """Fake que devolve payload pré-configurado. Implementa o Protocol LLMClient."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        self.chamadas: list[dict[str, Any]] = []

    def extrair_estruturado(
        self, system: str, user: str, schema: type[BaseModel], nome_ferramenta: str
    ) -> dict[str, Any]:
        self.chamadas.append({"system": system, "user": user, "ferramenta": nome_ferramenta})
        return self.payload


@pytest.fixture
def fake_llm() -> FakeLLMClient:
    return FakeLLMClient(
        payload={
            "acoes": [
                {
                    "descricao": "Enviar cronograma executivo do projeto",
                    "responsavel": "NETCON",
                    "prazo": "2025-12-03",
                    "status": "nao_iniciada",
                    "contexto_origem": "Netcon informou que enviará o cronograma executivo, até 03/12.",
                    "confianca": 0.9,
                }
            ],
            "resumo_documento": "Ata de KickOff do projeto Charqueadas.",
        }
    )
