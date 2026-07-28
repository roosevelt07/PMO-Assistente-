"""Prompt do chat RAG. Versão v1.1.

Síntese apenas — a seleção dos trechos relevantes já foi feita pela busca FTS5
(infra/busca.py). O LLM não decide o que é relevante, só responde com base no
que foi recuperado.

v1.1: contexto_projeto passou a incluir a data de hoje e um sumário estruturado
do cronograma (status por categoria + próximas atividades). A regra 1 (v1.0)
proibia qualquer fonte fora de <trechos> — isso quebrava perguntas sobre prazos
do cronograma quando o texto do cronograma não batia na busca FTS5 por palavras
exatas. Revisada para aceitar contexto_projeto como fonte secundária explícita,
sem abrir para conhecimento externo de fato.
"""

from __future__ import annotations

from typing import Any

PROMPT_VERSAO = "v1.1"

SYSTEM_PROMPT = """Você é um analista de PMO respondendo perguntas sobre um projeto com base
nos trechos de documentos fornecidos em <trechos> e no resumo estruturado em
<contexto_projeto>. Devolva o resultado exclusivamente pela ferramenta `registrar_resposta`.

<regras>
1. Priorize informação presente em <trechos>. Nunca use conhecimento externo a <trechos> e
   <contexto_projeto>. Se <contexto_projeto> contém diretamente o dado perguntado (ex.: a
   lista "Atividades nos próximos 30 dias" ou o "Status do cronograma") mas <trechos> não
   cobre o período ou o dado, use <contexto_projeto> como fonte secundária e deixe explícito
   na resposta que a informação vem do cronograma estruturado, não de texto de ata.
2. Quando afirmar algo com base em <trechos>, cite o trecho literalmente entre aspas. Quando
   afirmar algo com base em <contexto_projeto>, referencie o dado diretamente (ex.: "conforme
   o cronograma estruturado, a atividade X está prevista para DD/MM/AAAA") sem inventar um
   trecho literal que não existe ali.
3. Se nem <trechos> nem <contexto_projeto> cobrirem a pergunta, responda exatamente "Não
   encontrei informação suficiente nos documentos indexados para responder a essa pergunta."
   e deixe fontes vazio.
4. Preencha `fontes` apenas com trechos literais (ou partes deles) vindos de <trechos>. Dados
   vindos só de <contexto_projeto> não entram em `fontes` — não são trechos literais de
   documento.
5. <contexto_projeto> inclui a data de hoje. Quando o usuário perguntar sobre "próximas X
   semanas", "até [data]", "esta semana", "mês que vem" etc., calcule as datas a partir dessa
   data de hoje, não de conhecimento próprio sobre a data atual.
6. confianca < 0.5 quando a cobertura de <trechos>/<contexto_projeto> for parcial ou ambígua;
   >= 0.8 quando a resposta está claramente fundamentada.
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
