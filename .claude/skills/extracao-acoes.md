---
name: extracao-acoes
description: Acione ao editar o prompt de extração de ações, adicionar tipo de documento ou ajustar o schema de ações. Não acione para parser de cronograma, UI ou DB.
---

# Extração de Ações — Padrão do Projeto

## Checklist ao mexer em extração

1. Prompt vive em `core/prompts/extracao_acoes.py` — nunca inline em outro módulo.
2. Toda mudança de prompt incrementa `PROMPT_VERSAO` e adiciona teste em `tests/test_core.py`.
3. Schema de saída em `core/models.py::ResultadoExtracao`. Mudou? Atualize prompt + tabela ORM + migration.
4. Extração de dados estruturados usa SEMPRE tool use (`infra/llm.py`), nunca regex no texto do LLM.

## Padrões reais das atas (já no prompt v1.1)

- Atas KickOff: 90% informativo (escopo/preço/garantia). Ações em "OBSERVAÇÕES GERAIS" ou linhas com data/empresa explícita. Itens "Informativo" na coluna Data NÃO são ações.
- Status Report: "Atividades Realizadas" = histórico (ignore). Ações em "Próximas Atividades" e "Pontos de Atenção".
- Datas relativas ("03/12", "D+2") resolvidas com a data da reunião como âncora.

## Qualidade obrigatória

- `contexto_origem` é trecho LITERAL da ata (auditável), nunca paráfrase.
- `confianca < 0.5` em casos ambíguos — não infle.
- Ações duplicadas consolidadas em uma.

## Como testar sem queimar API

Use `FakeLLMClient` (em `tests/conftest.py`). O extrator depende do Protocol `LLMClient`, então testa sem chamar a Anthropic.
