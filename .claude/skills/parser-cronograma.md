---
name: parser-cronograma
description: Acione ao editar o parser de cronograma MS Project ou ao adicionar suporte a um novo layout de cronograma PDF. Não acione para extração de ações, UI ou DB.
---

# Parser de Cronograma — Padrão do Projeto

## Antes de tocar em `core/parsers/cronograma.py`

1. Rode `uv run pytest tests/test_parsers.py -q`. Os dois testes (Atiaia simples, Charqueadas baseline) DEVEM continuar verdes após qualquer mudança.
2. O parser é DETERMINÍSTICO. NUNCA introduza chamada a LLM aqui.

## Fatos sobre o texto extraído (pypdf)

- Extração é coluna-por-coluna, não linha-por-linha.
- Tarefa curta: tudo numa linha. Tarefa com nome longo: Id+nome em uma ou mais linhas, depois uma linha só com %/datas.
- Datas vêm COLADAS: `Qua 03/12/25Qui 09/07/26`. Use regex global de datas, não split.
- `%` pode vir colado ao nome: `Incêndio100%`.
- `ND` = data não definida → None. Preserve a posição (não pule o token).

## Dois layouts

- **Simples (Atiaia):** 1 percentual por linha → `percentual_esperado=None`, mapeia datas como início/término.
- **Baseline (Charqueadas):** 2 percentuais → `percentual_esperado` preenchido, mapeia 6 datas (BL início/término, início/término, real início/término).
- A detecção é pelo nº de `%` na linha. Não mude isso sem atualizar ambos os testes.

## Ao adicionar um novo layout

1. Adicione um trecho real (anonimizado) como constante de teste em `tests/test_parsers.py`.
2. Escreva o teste ANTES de mexer no parser (TDD).
3. Garanta que os layouts existentes continuam passando.

## Regra de atraso (em models.py, não no parser)

`TarefaCronograma.atrasada` é computed_field: atrasada se `%concluído < %esperado`, ou se `término > término_baseline` e `%concluído < 100`. Linha-resumo nunca conta como atrasada. Não duplique essa lógica no parser.
