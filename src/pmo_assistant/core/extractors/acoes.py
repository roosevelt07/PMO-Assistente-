"""Extrator de ações: orquestra prompt + LLM + validação Pydantic.

Função pura: depende da abstração LLMClient (Protocol), não da implementação.
Testável com fake. Não faz I/O de disco nem DB.
"""

from __future__ import annotations

from typing import Any, Protocol

from pmo_assistant.core.models import ResultadoExtracao, TipoDocumento
from pmo_assistant.core.prompts.extracao_acoes import SYSTEM_PROMPT, montar_user_prompt


class LLMClient(Protocol):
    """Contrato que infra/llm.py implementa. Definido em core para inverter dependência."""

    def extrair_estruturado(
        self, system: str, user: str, schema: type, nome_ferramenta: str
    ) -> dict[str, Any]: ...


NOME_FERRAMENTA = "registrar_acoes"
_MIN_CHARS = 100


def extrair_acoes(
    conteudo: str,
    tipo_documento: TipoDocumento,
    nome_arquivo: str,
    llm: LLMClient,
    data_referencia: str = "desconhecida",
) -> ResultadoExtracao:
    """Extrai ações de um documento de projeto.

    Raises:
        ValueError: conteúdo curto demais (provável PDF escaneado / erro de leitura).
        pydantic.ValidationError: payload do LLM inválido.
    """
    if len(conteudo.strip()) < _MIN_CHARS:
        raise ValueError(
            f"conteúdo curto ({len(conteudo.strip())} chars) — PDF escaneado ou erro de leitura"
        )

    user_prompt = montar_user_prompt(
        tipo_documento=tipo_documento.value,
        nome_arquivo=nome_arquivo,
        conteudo=conteudo,
        data_referencia=data_referencia,
    )
    payload = llm.extrair_estruturado(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        schema=ResultadoExtracao,
        nome_ferramenta=NOME_FERRAMENTA,
    )
    return ResultadoExtracao.model_validate(payload)
