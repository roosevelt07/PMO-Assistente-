---
name: extracao-atas
description: Acione ao adicionar um novo tipo de ata (kickoff, acompanhamento, handover, status report) ou ajustar o prompt de extração de ações. Não acione para mudanças em UI, DB ou RAG.
---

# Extração de Atas — Padrão do Projeto

## Checklist obrigatório ao mexer em extração

1. O prompt fica em `src/pmo_assistant/core/prompts/extracao_acoes.py` — NUNCA inline em outros módulos.
2. Toda mudança de prompt incrementa `PROMPT_VERSAO` no mesmo arquivo.
3. Toda mudança de prompt adiciona pelo menos um teste em `tests/test_extractors.py` validando o novo comportamento com `FakeLLMClient`.
4. Schema da saída vive em `core/models.py::ResultadoExtracao`. Mudou? Atualize:
   - prompt (instruções de preenchimento dos novos campos)
   - tabela ORM em `infra/db.py` se for persistir
   - migration Alembic
5. Adicionou novo `TipoDocumento`? Adicione caso de teste para esse tipo.

## Como NÃO extrair

- Não use regex para identificar ações no texto bruto. Deixe o LLM fazer com tool use.
- Não chame `anthropic.Anthropic` diretamente — use `infra/llm.py::LLMClient`.
- Não adicione lógica em `ui/app.py`; ela só orquestra.

## Critério de qualidade

Extração só é aceitável se:
- Todo campo `contexto_origem` é trecho LITERAL da ata, verificável.
- `confianca < 0.5` em casos ambíguos — não infle a confiança para parecer bom.
- Ações duplicadas (mesma atribuição em trechos diferentes) são consolidadas.
