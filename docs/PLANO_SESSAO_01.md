# Plano de Sessão Inicial — PMO Assistant

Cole este arquivo no Claude Code (ou referencie com `@docs/PLANO_SESSAO_01.md`)
ao iniciar o desenvolvimento. Use `/plan` antes de cada bloco para revisar sem editar.

## Pré-requisito

Leia o `CLAUDE.md` inteiro e me confirme em 3 frases: (a) os 3 objetivos, (b) a regra
de dependência, (c) por que o parser de cronograma não usa LLM. Não escreva código ainda.

## Sessão 1 — Persistência (fechar o ciclo de dados)

Hoje os dados extraídos vivem só em `st.session_state`. Implemente a gravação:

1. Em `infra/db.py`, adicione funções de repositório: `salvar_projeto`, `salvar_documento_com_acoes`, `salvar_cronograma`. Recebem schemas Pydantic de core, convertem para ORM, persistem.
2. Configure Alembic (`alembic init alembic`), gere a migration inicial a partir das tabelas existentes.
3. Conecte a UI: ao extrair ações ou analisar cronograma, persista e recarregue do banco.
4. Teste de integração: salvar e reler um projeto com ações e tarefas, conferir round-trip.

Critério de pronto: `uv run pytest -q` verde, incluindo o novo teste de round-trip. Lint e mypy limpos.

## Sessão 2 — Chat RAG (o "wow" da banca)

1. Em `infra/rag.py`, adicione chunking dos documentos (parágrafo ou janela de N tokens) e indexação ao salvar.
2. Crie `core/chat.py`: função pura que recebe pergunta + trechos recuperados + LLMClient e devolve resposta fundamentada (com citação do trecho de origem).
3. Implemente a aba "Chat do Projeto" no Streamlit usando esses dois.
4. Teste com `FakeLLMClient` e índice em memória.

Critério de pronto: perguntar "quais os riscos do projeto Charqueadas?" retorna resposta citando tarefas atrasadas reais.

## Armadilhas desta sessão

- Não persista `conteudo_bruto` gigante no SQLite sem necessidade — o RAG já guarda os trechos no Chroma.
- Migration Alembic: revise o SQL gerado antes de aplicar; autogenerate erra com tipos custom.
- Round-trip de datas: SQLite guarda como string ISO; confirme que volta como `date`.
