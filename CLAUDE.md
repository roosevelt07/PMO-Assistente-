# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

# PMO Assistant — Assistente de IA para Gerenciamento de Projetos

Projeto de TCC (MBA Gestão de Projetos). Objeto de estudo: um agente de IA que reduz
trabalho manual de PMO. Validado com documentos reais anonimizados de telecom/energia
(projetos Charqueadas e Barra dos Coqueiros, da Netcon).

---

## REGRAS CRÍTICAS (LEIA PRIMEIRO)

1. NUNCA especule sobre código que não leu. Leia o arquivo real antes de editar.
2. NUNCA invente campos em schemas. A verdade está em `src/pmo_assistant/core/models.py`.
3. NUNCA chame a API Anthropic fora de `infra/llm.py::LLMClient`. Extração de dados estruturados usa SEMPRE tool use com schema Pydantic — nunca regex em texto livre do LLM.
4. NUNCA quebre a regra de dependência: `ui → core`, `infra → core`, `core` não importa nada interno.
5. O parser de cronograma é DETERMINÍSTICO (regex). NUNCA o substitua por LLM — é o que mantém custo zero e resultado auditável.
6. SEMPRE rode `uv run pytest -q` antes de declarar uma task concluída.

---

## Os 3 objetivos (cada um amarrado ao TCC)

1. Extração de ações de atas/status reports → reduzir trabalho manual. (LLM + tool use)
2. Análise de cronograma MS Project (PDF) → monitorar prazos e desvios. (parser determinístico)
3. Saúde do projeto + chat RAG → apoio à decisão. (cruzamento de dados + RAG)

## Escopo do MVP (não expandir sem aprovação)

- Upload de ata KickOff (PDF/DOCX) e Status Report (PDF) → extração de ações
- Upload de cronograma MS Project exportado em PDF → tarefas + atrasos
- Dashboard de saúde cruzando ações pendentes e tarefas atrasadas, por projeto

Fora do MVP: chat RAG (esqueleto pronto, lógica na fase 2), handover, parsing de .mpp binário, análise preditiva.

---

## Stack

Python 3.11+ · `uv` (não pip/poetry) · `anthropic` (modelo `claude-sonnet-4-6`) ·
`pydantic` v2 · `sqlalchemy` 2.0 + `alembic` · `pypdf` + `python-docx` · `python-dotenv` ·
`streamlit` · `loguru` · `ruff` · `pytest` · `mypy --strict` (core/).

> `chromadb` e `sentence-transformers` foram **removidos** do `pyproject.toml` por incompatibilidade com Mac Intel.
> `infra/rag.py` ainda existe no repositório mas não deve ser importado por nada que rode agora.
> O chat RAG (objetivo 3) usa **SQLite FTS5** (`infra/busca.py`), não embeddings — o SDK
> `anthropic` não tem endpoint de embeddings (`client.embeddings` não existe); `voyage-multilingual-2`
> é da Voyage AI, um provedor separado com chave própria. Ver armadilha abaixo.

---

## Arquitetura (regra de dependência)

```
src/pmo_assistant/
├── core/        # PURO. Não importa infra/ nem ui/.
│   ├── models.py            # schemas Pydantic (verdade canônica — leia antes de qualquer edição)
│   ├── extractors/acoes.py  # extração de ações (Protocol LLMClient + função pura)
│   ├── parsers/cronograma.py# parser MS Project PDF (regex, sem LLM)
│   ├── saude.py             # cruzamento cronograma + ações → SaudeProjeto
│   ├── chat.py               # RAG: sintetiza resposta a partir de trechos já recuperados (Protocol LLMClient)
│   └── prompts/             # prompts versionados como módulos Python (extracao_acoes.py, chat.py)
├── infra/       # adaptadores I/O
│   ├── llm.py       # Anthropic + tool use + retry/jitter + cache em disco
│   ├── cache.py     # SHA-256(modelo|ferramenta|system|user) → JSON em data/cache/llm/
│   ├── docs.py      # leitura PDF/DOCX, detecta escaneado, dedup células mescladas
│   ├── db.py        # SQLAlchemy 2.0 declarativo + WAL; ORM: ProjetoORM, DocumentoORM (com conteudo_bruto), AcaoORM, TarefaORM
│   ├── repositorio.py # funções de persistência (Session → ORM → commit)
│   ├── busca.py      # chunking + índice full-text SQLite FTS5 (tabela virtual documentos_fts) — RAG do objetivo 3
│   └── rag.py       # ChromaDB singleton (não importar — chromadb removido do pyproject; substituído por busca.py)
├── ui/app.py    # Streamlit (3 abas) — só orquestra; load_dotenv() no topo
└── cli.py       # Typer: init-db, limpar-cache
```

### Como o DB é instanciado

`criar_engine(caminho?)` retorna Engine com WAL + foreign_keys habilitados.
`criar_session_factory(engine)` retorna `sessionmaker(expire_on_commit=False)`.
`inicializar_schema(engine)` cria tabelas via metadata (apenas dev; produção usa Alembic).
Arquivo padrão: `data/pmo.db`.

### Como o LLM é chamado

`LLMClient.extrair_estruturado(system, user, schema, nome_ferramenta)` força `tool_choice`
e valida `stop_reason == "tool_use"`. Toda chamada passa pelo cache em disco antes de
bater na API. Para testes use `FakeLLMClient` de `tests/conftest.py`.

---

## Comandos

```bash
uv sync
uv run streamlit run src/pmo_assistant/ui/app.py   # inicia na porta 8501 (ou próxima livre)
uv run python -m pmo_assistant.cli init-db          # cria data/pmo.db
uv run python -m pmo_assistant.cli limpar-cache     # rm -rf data/cache/llm/
uv run pytest -q                                    # todos os testes
uv run pytest -q tests/test_parsers.py              # um módulo só
uv run pytest -q tests/test_parsers.py::test_parser_charqueadas_baseline  # um teste só
uv run ruff check src/ tests/
uv run mypy src/pmo_assistant/core/
```

---

## Convenções

- Type hints obrigatórios. Sem `except Exception:` genérico (exceção: superfície de UI no Streamlit, que loga e mostra).
- Retry externo: backoff exponencial + jitter `min(60, 2**n) + random(0,1)`.
- Domínio em português (Acao, Tarefa, Responsavel); infra em inglês (Client, Cache, Repository).
- Funções > 50 linhas: comentário no porquê, não no o quê.

---

## Cache de LLM (OBRIGATÓRIO)

Toda chamada via `LLMClient` passa por `infra/cache.py` (hash do prompt → JSON).
Em dev você roda os mesmos testes muitas vezes — sem cache, queima crédito à toa.
Limpar: `rm -rf data/cache/llm/`.

---

## Armadilhas Conhecidas (validadas com docs reais)

- **Cronograma PDF, não .mpp:** `pypdf` extrai COLUNA por COLUNA — nomes longos quebram em 2-3 linhas e datas vêm coladas (`Qua 03/12/25Qui 09/07/26`). O parser usa máquina de estados com buffer de nome. NÃO simplifique para split por espaços.
- **Dois layouts de cronograma:** Atiaia tem 5 colunas (sem baseline); Charqueadas tem baseline + % esperado. O parser detecta pelo nº de `%` na linha. Ambos têm teste em `tests/test_parsers.py` — não quebre nenhum.
- **Atas são 90% informativas:** a maioria das linhas é escopo/preço/garantia com "Informativo" na coluna Data. Ações reais ficam em "OBSERVAÇÕES GERAIS". O prompt v1.1 já trata isso — se mudar o prompt, incremente a versão e adicione teste.
- **DOCX com células mescladas:** atas DOCX repetem a mesma célula 4x (merge). `infra/docs.py` deduplica células consecutivas iguais. Não remova essa dedup.
- **Tool use pode falhar:** o modelo às vezes ignora `tool_choice`. `llm.py` checa `stop_reason == "tool_use"` e levanta erro claro. Mantenha.
- **`TarefaORM` não tem `eh_resumo`:** o campo existe em `TarefaCronograma` (Pydantic), mas não na tabela ORM. Ao persistir, ignore tarefas com `eh_resumo=True` ou persista sem o campo — nunca crie uma coluna nova sem migration Alembic.
- **`ANTHROPIC_API_KEY` via `.env`:** `ui/app.py` chama `load_dotenv()` no topo. Fora do Streamlit (CLI, testes de integração), chame `load_dotenv()` explicitamente antes de instanciar `LLMClient`, ou defina a variável no ambiente.
- **Streamlit não roda async no main thread.** Mantenha funções síncronas.
- **SDK `anthropic` não tem embeddings:** `client.embeddings` não existe (verificado com `anthropic==0.111.0`). `voyage-multilingual-2` é da Voyage AI, provedor separado com `VOYAGE_API_KEY` próprio. Por isso o chat RAG usa SQLite FTS5 (`infra/busca.py`), não similaridade semântica. Se algum dia trocar para embeddings de verdade, isso é uma decisão de arquitetura nova (nova dependência `voyageai`, nova chave) — não assuma que existe via `LLMClient`.
- **Alembic autogenerate não reflete tabelas virtuais FTS5:** `documentos_fts` é criada via `op.execute("CREATE VIRTUAL TABLE ...")` manual na migration `add_conteudo_bruto_fts` — autogenerate nunca vai detectar mudanças nela. Se alterar as colunas do FTS5, escreva a migration à mão.
- **`bm25()` do FTS5 é negativo:** quanto menor (mais negativo), mais relevante — não existe limiar universal tipo cosine 0.5. `infra/busca.py::buscar` usa "lista vazia = sem resultado" em vez de um score mínimo.

---

## Critérios de "task concluída"

1. `uv run pytest -q` verde
2. `uv run ruff check` limpo
3. `uv run mypy` passa no código tocado de core/
4. Mudou schema ORM → rodou migration Alembic e revisou
5. Comportamento novo tem teste (não só caminho feliz)
