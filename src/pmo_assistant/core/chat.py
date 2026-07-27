"""Chat RAG: sintetiza resposta a partir de trechos já recuperados por busca full-text.

Função pura: depende da abstração LLMClient (Protocol), não de infra/. Não decide quais
trechos são relevantes — isso é feito por infra/busca.py::buscar. Testável com fake.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pmo_assistant.core.models import RespostaChat
from pmo_assistant.core.prompts.chat import SYSTEM_PROMPT, montar_user_prompt

if TYPE_CHECKING:
    from pmo_assistant.core.extractors.acoes import LLMClient

NOME_FERRAMENTA = "registrar_resposta"

_RESPOSTA_SEM_TRECHOS = (
    "Não encontrei informação suficiente nos documentos indexados para responder a essa "
    "pergunta."
)


def responder_pergunta(
    pergunta: str,
    trechos_recuperados: list[dict[str, Any]],
    contexto_projeto: str,
    llm: LLMClient,
) -> RespostaChat:
    """Responde uma pergunta com base nos trechos já recuperados.

    Se não houver trechos, retorna direto sem chamar o LLM (evita custo e alucinação
    sobre contexto vazio).
    """
    if not trechos_recuperados:
        return RespostaChat(resposta=_RESPOSTA_SEM_TRECHOS, fontes=[], confianca=0.0)

    user_prompt = montar_user_prompt(
        pergunta=pergunta,
        trechos_recuperados=trechos_recuperados,
        contexto_projeto=contexto_projeto,
    )
    payload = llm.extrair_estruturado(
        system=SYSTEM_PROMPT,
        user=user_prompt,
        schema=RespostaChat,
        nome_ferramenta=NOME_FERRAMENTA,
    )
    return RespostaChat.model_validate(payload)
