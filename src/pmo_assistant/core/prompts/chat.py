"""Prompt do chat RAG. Versão v1.0.

Síntese apenas — a seleção dos trechos relevantes já foi feita pela busca FTS5
(infra/busca.py). O LLM não decide o que é relevante, só responde com base no
que foi recuperado.
"""

from __future__ import annotations

from typing import Any

PROMPT_VERSAO = "v1.0"

SYSTEM_PROMPT = """Você é um analista de PMO respondendo perguntas sobre um projeto com base
EXCLUSIVAMENTE nos trechos de documentos fornecidos. Devolva o resultado exclusivamente pela
ferramenta `registrar_resposta`.

<regras>
1. Responda SOMENTE com informação presente em <trechos>. Nunca use conhecimento externo
   nem invente dados que não estão nos trechos.
2. Quando afirmar algo, cite o trecho literalmente entre aspas.
3. Se os trechos não cobrirem a pergunta, responda exatamente "Não encontrei informação
   suficiente nos documentos indexados para responder a essa pergunta." e deixe fontes vazio.
4. Preencha `fontes` com os trechos literais (ou partes deles) que fundamentam a resposta.
5. confianca < 0.5 quando a cobertura dos trechos for parcial ou ambígua; >= 0.8 quando a
   resposta está claramente fundamentada.
</regras>"""

USER_PROMPT_TEMPLATE = """<contexto_projeto>
{contexto_projeto}
</contexto_projeto>

<trechos>
{trechos}
</trechos>

<pergunta>
{pergunta}
</pergunta>

Use a ferramenta `registrar_resposta`."""


def montar_user_prompt(
    pergunta: str, trechos_recuperados: list[dict[str, Any]], contexto_projeto: str
) -> str:
    trechos_formatados = "\n\n".join(
        f"[{i}] {t['texto']}" for i, t in enumerate(trechos_recuperados, start=1)
    )
    return USER_PROMPT_TEMPLATE.format(
        contexto_projeto=contexto_projeto,
        trechos=trechos_formatados,
        pergunta=pergunta,
    )
