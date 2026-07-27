<div align="center">

<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:0a1a0a,50:1B4332,100:40916C&height=160&section=header&text=PMO%20Assistente&fontSize=48&fontColor=ffffff&fontAlignY=40&desc=%F0%9F%93%8A%20An%C3%A1lise%20Inteligente%20de%20Projetos%20%7C%20Atas%20%C2%B7%20Cronograma%20%C2%B7%20Chat%20RAG&descAlignY=65&descSize=14&animation=fadeIn" />

![Python](https://img.shields.io/badge/Python_3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?style=for-the-badge&logo=streamlit&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite_FTS5-003B57?style=for-the-badge&logo=sqlite&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic_v2-E92063?style=for-the-badge&logo=pydantic&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy_2.0-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)

</div>

---

> 📊 Solução desenvolvida para escritórios de projetos (PMO) de empresas de infraestrutura, telecomunicações e energia — automatiza a análise de documentos, centraliza o histórico de atas e cronogramas e entrega visibilidade real do andamento dos projetos em uma interface única.

---

## 🧭 Visão Geral

O **PMO Assistente** é um agente de análise de projetos que processa documentos reais de gestão — atas de reunião, relatórios de status e cronogramas MS Project — e entrega três capacidades em uma interface unificada:

**Antes:** Ata de reunião recebida por e-mail → leitura manual → extração manual de ações → registro em planilha → risco real de omissão ou erro de responsável.

**Depois:** Upload do PDF → extração automática de todas as ações com responsável, prazo e status → persistência no banco → histórico consultável por chat.

---

## 📈 Resultados

| Métrica | Antes | Depois |
|:---|:---|:---|
| Extração de ações | Manual, linha por linha | **Automática com schema estruturado validado** |
| Análise de cronograma | Abertura do MS Project | Parser determinístico sobre PDF exportado |
| Saúde do projeto | Calculada manualmente | **Dashboard com NivelSaude automático** |
| Histórico de documentos | Pastas de e-mail | Banco SQLite com busca FTS5 por conteúdo |
| Consulta sobre documentos | Releitura dos arquivos | **Chat RAG com citação de trechos** |

---

## ⚙️ Como Funciona

```
┌─────────────────────────────────────────────────────────────────────┐
│                          GESTOR PMO                                  │
│                                                                      │
│   Upload de ata PDF/DOCX → Upload de cronograma PDF → Perguntas     │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     INTERFACE (Streamlit)                            │
│                                                                      │
│   Aba Ações de Atas │ Aba Cronograma & Saúde │ Aba Chat do Projeto  │
└──────────────────────────────┬──────────────────────────────────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                 ▼
┌─────────────────┐  ┌──────────────────┐  ┌──────────────────────┐
│  EXTRATOR DE    │  │  PARSER DE       │  │  CHAT RAG            │
│  AÇÕES          │  │  CRONOGRAMA      │  │                      │
│                 │  │  (determinístico)│  │  FTS5 + motor NLP    │
│  Schema         │  │                 │  │  (SQLite nativo)      │
│  estruturado    │  │  avaliar_saude() │  │                      │
│  AcaoExtraida   │  │  NivelSaude     │  │  Citação de trechos  │
└────────┬────────┘  └────────┬─────────┘  └──────────┬───────────┘
         │                    │                        │
         └────────────────────┼────────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    SQLite (Alembic migrations)                       │
│                                                                      │
│   Projeto → Documento (conteudo_bruto) → Ação → Tarefa              │
│   documentos_fts (tabela virtual FTS5 — busca full-text/BM25)       │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🗂️ Três Abas, Três Capacidades

### 📋 Aba 1 — Ações de Atas

Upload de ata de reunião (PDF ou DOCX) → o sistema processa o texto com schema estruturado `AcaoExtraida` (Pydantic v2) e extrai todas as ações com responsável, prazo e status, retornando JSON validado. O resultado é persistido no banco e exibido em tabela filtrável por status e responsável.

- Suporte a PDF e DOCX via `pymupdf` + `python-docx`
- Cache em disco por SHA-256 do conteúdo — documentos processados não são reprocessados
- Tipos de documento: ata de kickoff, reunião de andamento, status report

### 📊 Aba 2 — Cronograma & Saúde

Upload do cronograma exportado do MS Project em PDF → parser determinístico extrai tarefas, percentuais concluídos, datas de baseline e término real. A função `avaliar_saude()` calcula o `NivelSaude` do projeto (NO_PRAZO / EM_RISCO / ATRASADO) com base no desvio entre previsto e realizado.

- Análise 100% determinística — zero dependência externa
- Dashboard com 3 cards de métricas coloridos por nível de saúde
- Gráfico de barras de status das tarefas
- Lista de tarefas atrasadas com detalhamento

### 💬 Aba 3 — Chat do Projeto

Chat com histórico sobre os documentos do projeto. A busca usa **SQLite FTS5** com BM25 (sem embeddings externos, sem dependências compiladas) — top-5 trechos recuperados alimentam o motor de síntese com citação literal de fonte.

- Indexação automática no upload do documento
- Reindexação idempotente no boot
- Resposta com expander de fontes citadas
- Histórico de conversa em `session_state`

---

## 🛠️ Stack Técnica

| Camada | Tecnologia | Decisão |
|:---|:---|:---|
| Interface | **Streamlit** | Interface web sem necessidade de infraestrutura adicional |
| Motor de análise | **API de linguagem** | Extração estruturada com schema Pydantic validado |
| ORM | **SQLAlchemy 2.0** + Alembic | Migrations versionadas, type-safe com `Mapped[]` |
| Banco | **SQLite** + FTS5 | Zero configuração, busca full-text nativa, portável |
| Validação | **Pydantic v2** | Schema canônico compartilhado entre motor e ORM |
| Leitura de docs | **pymupdf** + **python-docx** | PDF e DOCX sem servidor de conversão |
| Gerenciamento | **uv** | Resolução de dependências determinística |
| Testes | **pytest** | 34 testes cobrindo core/ e infra/ |
| Qualidade | **ruff** + **mypy** (strict em core/) | Zero erros de tipo no domínio de negócio |

---

## 🏗️ Decisões Arquiteturais

### Por que schema estruturado em vez de parsing de texto livre?

O motor de análise responde com JSON que satisfaz o schema `AcaoExtraida` — Pydantic valida na entrada. Parsing de texto livre (regex sobre markdown) quebra com variações de formato. Schema estruturado garante que `responsavel`, `prazo` e `status` sempre chegam tipados ou a chamada falha com erro rastreável.

### Por que SQLite FTS5 em vez de embeddings (ChromaDB, FAISS)?

Duas razões concretas: (1) ChromaDB e sentence-transformers dependem de PyTorch compilado, incompatível com Mac Intel — o ambiente de desenvolvimento real. (2) O domínio é um único projeto com vocabulário especializado e consistente — o gestor pergunta com os mesmos termos que estão na ata. FTS5 com BM25 resolve 90%+ dos casos sem dependência externa e com busca auditável via `sqlite3`.

### Por que separar `core/` de `infra/`?

A regra de dependência é unidirecional: `ui/ → core/`, `ui/ → infra/`, `core/` nunca importa `infra/`. Isso garante que toda lógica de negócio (extração, parsing, avaliação de saúde, chat) é testável sem banco, sem rede e sem Streamlit — os 34 testes rodam em qualquer ambiente com `uv run pytest`.

### Por que cache por SHA-256 do conteúdo?

O cache em `data/cache/llm/` serializa a resposta do motor por hash do texto — documentos já processados não são reprocessados em execuções subsequentes, reduzindo latência e custo operacional.

---

## 📁 Estrutura do Projeto

```
pmo-assistant/
├── src/pmo_assistant/
│   ├── core/                        # Domínio puro — zero I/O
│   │   ├── models.py                # AcaoExtraida, Cronograma, NivelSaude, RespostaChat
│   │   ├── extractors/acoes.py      # Extração com schema estruturado
│   │   ├── parsers/cronograma.py    # Parser determinístico MS Project PDF
│   │   ├── saude.py                 # avaliar_saude() → NivelSaude
│   │   ├── chat.py                  # Síntese RAG com citação de trechos
│   │   └── prompts/                 # Prompts por tarefa
│   ├── infra/                       # I/O: banco, motor, docs, busca
│   │   ├── db.py                    # ORM SQLAlchemy 2.0 (ProjetoORM, DocumentoORM, AcaoORM, TarefaORM)
│   │   ├── repositorio.py           # CRUD — única camada que toca o banco
│   │   ├── llm.py                   # Motor de análise com retry/jitter/cache
│   │   ├── docs.py                  # ler_documento() — PDF e DOCX
│   │   └── busca.py                 # FTS5: indexar + buscar (BM25)
│   └── ui/
│       └── app.py                   # Streamlit — só orquestra core/ e infra/
├── alembic/                         # Migrations versionadas
│   └── versions/
│       ├── ..._schema_inicial.py
│       └── ..._add_conteudo_bruto_fts.py
├── tests/                           # 34 testes com fakes (sem rede, sem banco real)
│   ├── test_core.py
│   ├── test_parsers.py
│   ├── test_repositorio.py
│   ├── test_busca.py
│   └── test_chat.py
├── .streamlit/config.toml           # Tema (paleta verde escuro)
├── pyproject.toml
└── README.md
```

---

## 🚀 Instalação e Execução

### Pré-requisitos

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) instalado
- Chave de API configurada no `.env`

### Passos

```bash
# 1. Clone o repositório
git clone https://github.com/roosevelt07/pmo-assistant.git
cd pmo-assistant

# 2. Instale as dependências
uv sync

# 3. Configure as variáveis de ambiente
cp .env.example .env
# Edite .env com suas credenciais

# 4. Inicialize o banco e aplique as migrations
uv run alembic upgrade head

# 5. Suba a aplicação
uv run streamlit run src/pmo_assistant/ui/app.py
```

Acesse `http://localhost:8501` no browser.

### Executar testes

```bash
uv run pytest -q                          # 34 testes — zero dependências externas
uv run mypy src/pmo_assistant/core/       # type check no domínio
uv run ruff check src/ tests/             # lint
```

---

## 📄 Licença

Copyright (c) 2026 Roosevelt Bispo. Todos os direitos reservados.

Este projeto é proprietário e confidencial. Nenhuma parte do código-fonte pode ser reproduzida, distribuída ou modificada sem autorização prévia e por escrito do autor.

Para licenciamento ou uso: roosevelt.bispo777@gmail.com

---

## 👤 Autor

**Roosevelt Bispo** — Engenheiro de Software | Python · TypeScript · Automação

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=flat-square&logo=linkedin&logoColor=white)](https://linkedin.com/in/roosevelt-bispo)
[![GitHub](https://img.shields.io/badge/GitHub-181717?style=flat-square&logo=github&logoColor=white)](https://github.com/roosevelt07)

---

<div align="center">
<img width="100%" src="https://capsule-render.vercel.app/api?type=waving&color=0:40916C,50:1B4332,100:0a1a0a&height=80&section=footer&animation=fadeIn" />
</div>
