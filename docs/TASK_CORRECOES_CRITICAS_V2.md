# TASK — Correções Críticas: Parser Universal + Dashboard + Chat com Cronograma
# Salve em: pmo-assistant/docs/TASK_CORRECOES_CRITICAS_V2.md
# No terminal: claude → @docs/TASK_CORRECOES_CRITICAS_V2.md

---

## LEIA ANTES DE QUALQUER COISA

Leia integralmente nesta ordem:
1. `CLAUDE.md`
2. `src/pmo_assistant/core/models.py`
3. `src/pmo_assistant/core/parsers/cronograma.py` — **inteiro, linha por linha**
4. `src/pmo_assistant/infra/busca.py` — funções `indexar` e `buscar`
5. `src/pmo_assistant/infra/repositorio.py`
6. `src/pmo_assistant/core/relatorio.py`
7. `src/pmo_assistant/ui/app.py` — blocos `with aba_crono:` e `with aba_chat:` completos

Use `/plan` e confirme em 5 frases antes de codificar:
(a) por que o cronograma da Tripla mostrou 0% e qual a causa raiz no parser
(b) como o texto do cronograma vai entrar no FTS5 sem quebrar a regra core/ → infra/
(c) onde exatamente o gráfico de pizza será inserido na aba Cronograma
(d) como o chat vai saber a data de hoje para responder "próximas 2 semanas"
(e) quais arquivos serão tocados e quais não serão

---

## CONTEXTO DOS DOCUMENTOS REAIS

Dois layouts de cronograma coexistem no mesmo sistema:

**Layout A — MS Project exportado (Charqueadas, Grantel-Axia):**
Colunas: `Id | Modo | Nome da Tarefa | % concluída | % Expected Task | Início da Linha de Base | Término da linha de base | Início | Término | Início real | Término real`
Linha-resumo raiz: `id_tarefa == 1`, contém os agregados do projeto todo.
Datas em português: `Qua 03/12/25`, `Ter 11/08/26`.
Linhas `eh_resumo=True`: fases como INICIALIZAÇÃO, PLANEJAMENTO, EXECUÇÃO etc.

**Layout B — Dashboard Executivo (Tripla, Usina Santo Antônio):**
Colunas: `ID | Resp. | Início Prev. | Conclusão Prev. | Status | % Execução`
IDs no formato `1.1`, `1.2`, `2.1` — não inteiros sequenciais.
Status literal: `Concluído`, `A Iniciar`, `Em Andamento`.
Sem colunas de baseline. Sem linha-resumo de projeto.
Resumo no topo: `Total=41, Concluídas=30, A Iniciar=11, Progresso=73%`.

O parser atual só lê Layout A. Cronogramas Layout B retornam `Cronograma` com lista vazia
ou zeros — causando `0% concluído, 0 tarefas atrasadas, saúde=no_prazo` incorretamente.

---

## PROBLEMA 1 — Parser silenciosamente falha em cronogramas Layout B

### Causa raiz
`parsear_cronograma()` procura colunas por nome exato em português do MS Project.
Se não encontra `% concluída` e `% Expected Task`, não extrai nenhuma tarefa mas
**não levanta exceção** — retorna `Cronograma` vazio sem aviso ao usuário.

### Solução

**Parte 1A — Detecção de layout antes do parsing:**

Em `core/parsers/cronograma.py`, adicione função `detectar_layout(texto: str) -> str`
que retorna `"ms_project"` ou `"dashboard_executivo"` ou `"desconhecido"`:

```python
def detectar_layout(texto: str) -> str:
    """Detecta o formato do PDF de cronograma pelo conteúdo textual.
    
    MS Project: contém cabeçalhos específicos em português do MS Project.
    Dashboard Executivo: contém estrutura de resumo com totais e IDs decimais.
    """
    if "% Expected" in texto or "Início da Linha de Base" in texto:
        return "ms_project"
    if "A Iniciar" in texto and "Concluído" in texto and "Resp." in texto:
        return "dashboard_executivo"
    return "desconhecido"
```

**Parte 1B — Parser para Layout B (Dashboard Executivo):**

Crie `_parsear_dashboard_executivo(texto: str, projeto_id: int, nome_projeto: str) -> Cronograma`.

Extração do resumo do topo (regex robusta, Layout B tem linha como):
`"✓ Concluído 30 73%"` ou `"⚙ Total Geral 41 100%"` ou tabela `Status | Qtd. | % Total`

```python
import re

def _extrair_resumo_dashboard(texto: str) -> dict:
    """Extrai totais do bloco de resumo do Dashboard Executivo.
    
    Busca padrões como: 'Concluído NNN' e 'Total Geral NNN'
    Robusto a variações de emoji e espaçamento.
    """
    resultado = {"total": 0, "concluidas": 0, "a_iniciar": 0, "em_andamento": 0, "percentual": 0.0}
    
    # Total geral
    m = re.search(r'Total\s+Geral\s+(\d+)', texto, re.IGNORECASE)
    if m:
        resultado["total"] = int(m.group(1))
    
    # Concluídas
    m = re.search(r'Conclu[ií]d[ao]\s+(\d+)\s+(\d+)%', texto, re.IGNORECASE)
    if m:
        resultado["concluidas"] = int(m.group(1))
        resultado["percentual"] = float(m.group(2))
    
    # A Iniciar
    m = re.search(r'A\s+Iniciar\s+(\d+)', texto, re.IGNORECASE)
    if m:
        resultado["a_iniciar"] = int(m.group(1))
    
    return resultado
```

Cada linha de tarefa do Layout B gera um `TarefaCronograma` com:
- `id_tarefa`: int extraído do ID (ex: `1.1` → hash inteiro único, ou sequencial simples)
- `nome`: nome da atividade da coluna "Atividades"
- `percentual_concluido`: 100.0 se status="Concluído", 0.0 se "A Iniciar", 50.0 se "Em Andamento"
- `percentual_esperado`: None (Layout B não tem baseline)
- `inicio`: data de "Início Prev." se disponível
- `termino`: data de "Conclusão Prev." se disponível
- `inicio_real`: None se "A Iniciar", igual a `inicio` se "Concluído"
- `termino_real`: data de "Conclusão Prev." se status="Concluído", None caso contrário
- `eh_resumo`: False para todas (Layout B não tem hierarquia)

Para o Layout B, a linha-resumo sintética (id_tarefa=1) é gerada a partir do resumo do topo:
```python
resumo_sintetico = TarefaCronograma(
    id_tarefa=1,
    nome=nome_projeto,
    percentual_concluido=resumo["percentual"],
    percentual_esperado=100.0,  # Layout B não tem expected — assume 100% como meta
    eh_resumo=True,
)
```

**Parte 1C — Atualizar `parsear_cronograma()` para chamar o parser correto:**

```python
def parsear_cronograma(conteudo: str, projeto_id: int, nome_projeto: str) -> Cronograma:
    layout = detectar_layout(conteudo)
    if layout == "ms_project":
        return _parsear_ms_project(conteudo, projeto_id, nome_projeto)
    elif layout == "dashboard_executivo":
        return _parsear_dashboard_executivo(conteudo, projeto_id, nome_projeto)
    else:
        # Layout desconhecido — tenta MS Project como fallback, avisa no log
        logger.warning("Layout de cronograma não reconhecido — tentando MS Project como fallback")
        return _parsear_ms_project(conteudo, projeto_id, nome_projeto)
```

Renomeie a implementação atual de `parsear_cronograma` para `_parsear_ms_project`.

**Parte 1D — Feedback visual quando layout é desconhecido:**

Em `ui/app.py`, após chamar `parsear_cronograma()`, verifique se `cr.tarefas` está vazio:
```python
if not cr.tarefas:
    st.warning(
        "Nenhuma tarefa foi extraída do cronograma. "
        "Verifique se o PDF está no formato MS Project ou Dashboard Executivo. "
        "Tente exportar novamente com todas as colunas visíveis."
    )
```

---

## PROBLEMA 2 — Dashboard incompleto (só mostra atrasadas)

### Solução: 4 seções + gráfico de pizza

Em `ui/app.py`, dentro de `with aba_crono:`, no bloco `if cr:`, após os 3 cards e
**antes** da seção "Status Report para o Cliente", substitua o bloco atual de
"tarefas atrasadas" por 4 seções expandíveis + gráfico de pizza.

**Gráfico de pizza com plotly (já disponível como dep transitiva ou instale):**

Verifique se `plotly` está em `pyproject.toml`. Se não estiver, adicione:
```toml
"plotly>=5.0.0",
```
E regenere: `uv sync && uv export --no-hashes --format requirements-txt > requirements.txt`

**Código da seção de dashboard expandido:**

```python
from pmo_assistant.core.relatorio import classificar_tarefas_por_status

# Classificação
contagem = classificar_tarefas_por_status(cr.tarefas)
folhas = [t for t in cr.tarefas if not t.eh_resumo]

# Gráfico de pizza
import plotly.graph_objects as go

labels = list(contagem.keys())
values = list(contagem.values())
cores = {
    "Concluída": "#40916C",
    "No Prazo": "#4361EE",
    "Atrasada": "#E63946",
    "Tarefa Futura": "#ADB5BD",
}
fig = go.Figure(data=[go.Pie(
    labels=labels,
    values=values,
    marker_colors=[cores[l] for l in labels],
    hole=0.4,
    textinfo="label+percent",
    showlegend=True,
)])
fig.update_layout(
    margin=dict(t=0, b=0, l=0, r=0),
    height=320,
    showlegend=True,
    legend=dict(orientation="h", y=-0.1),
)
st.plotly_chart(fig, use_container_width=True)

# 4 expanders com tabelas
from pmo_assistant.core.relatorio import (
    atividades_realizadas, proximas_atividades, pontos_de_atencao
)

# Tarefas futuras = não iniciadas (inicio_real is None) e não atrasadas e % < 100
tarefas_futuras = [
    t for t in folhas
    if t.inicio_real is None and not t.atrasada and t.percentual_concluido < 100
]

def _fmt_data(d) -> str:
    return d.strftime("%d/%m/%Y") if d else "—"

def _tabela_tarefas(tarefas, colunas_datas):
    """Renderiza st.dataframe com as colunas especificadas."""
    if not tarefas:
        return None
    rows = []
    for t in tarefas:
        row = {"Tarefa": t.nome[:80], "% Concluído": f"{t.percentual_concluido:.0f}%"}
        for label, campo in colunas_datas:
            row[label] = _fmt_data(getattr(t, campo, None))
        rows.append(row)
    return rows

with st.expander(f"✅ Concluídas ({contagem['Concluída']})", expanded=False):
    realizadas = atividades_realizadas(cr.tarefas)
    dados = _tabela_tarefas(realizadas, [("Prevista", "termino_baseline"), ("Concluída em", "termino_real")])
    if dados:
        st.dataframe(dados, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma atividade concluída.")

with st.expander(f"🟢 No Prazo ({contagem['No Prazo']})", expanded=False):
    no_prazo = proximas_atividades(cr.tarefas)
    dados = _tabela_tarefas(no_prazo, [("Prevista", "termino_baseline"), ("Nova Previsão", "termino")])
    if dados:
        st.dataframe(dados, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma atividade em andamento no prazo.")

with st.expander(f"🔴 Atrasadas ({contagem['Atrasada']})", expanded=True):
    atrasadas = pontos_de_atencao(cr.tarefas)
    dados = _tabela_tarefas(atrasadas, [("Prevista", "termino_baseline"), ("Atual", "termino")])
    if dados:
        st.dataframe(dados, use_container_width=True, hide_index=True)
    else:
        st.success("Nenhuma tarefa atrasada detectada.")

with st.expander(f"⏳ Atividades Futuras ({contagem['Tarefa Futura']})", expanded=False):
    dados = _tabela_tarefas(tarefas_futuras, [("Início Previsto", "inicio"), ("Conclusão Prevista", "termino")])
    if dados:
        st.dataframe(dados, use_container_width=True, hide_index=True)
    else:
        st.info("Nenhuma atividade futura identificada.")
```

**Remova** o bloco antigo `st.subheader("Tarefas Atrasadas")` + `st.dataframe` simples
que só mostrava atrasadas — está sendo substituído pelas 4 seções acima.

---

## PROBLEMA 3 — Chat não lê dados do cronograma

### Causa raiz
O fluxo atual: upload do cronograma → `parsear_cronograma()` → `salvar_cronograma()`
→ dados vão para `TarefaORM`. O texto bruto do PDF nunca entra no FTS5.
`buscar()` só encontra texto de atas.

### Solução: indexar texto estruturado do cronograma no FTS5

Após `salvar_cronograma()` em `ui/app.py`, construa e indexe um texto estruturado
representando o cronograma — **sem mudar a assinatura de `reindexar_documento()`**:

```python
# Em ui/app.py, logo após salvar_cronograma():
from pmo_assistant.infra.busca import reindexar_documento

def _texto_cronograma_para_fts(cr: Cronograma) -> str:
    """Serializa o cronograma como texto pesquisável pelo FTS5.
    
    Inclui nome, datas e status de cada tarefa — preserva termos que o usuário
    usará em perguntas: "próximas atividades", "atrasadas", datas específicas.
    """
    linhas = [f"Cronograma do projeto: {cr.nome_projeto}"]
    if cr.data_referencia:
        linhas.append(f"Data de referência: {cr.data_referencia.strftime('%d/%m/%Y')}")
    
    for t in cr.tarefas:
        if t.eh_resumo:
            continue
        status = "concluída" if t.percentual_concluido >= 100 else (
            "atrasada" if t.atrasada else (
                "futura" if t.inicio_real is None else "em andamento"
            )
        )
        partes = [f"Atividade: {t.nome}. Status: {status}."]
        partes.append(f"Percentual concluído: {t.percentual_concluido:.0f}%.")
        if t.termino_baseline:
            partes.append(f"Previsão original: {t.termino_baseline.strftime('%d/%m/%Y')}.")
        if t.termino:
            partes.append(f"Término previsto: {t.termino.strftime('%d/%m/%Y')}.")
        if t.inicio:
            partes.append(f"Início previsto: {t.inicio.strftime('%d/%m/%Y')}.")
        if t.termino_real:
            partes.append(f"Concluída em: {t.termino_real.strftime('%d/%m/%Y')}.")
        linhas.append(" ".join(partes))
    
    return "\n".join(linhas)
```

Após `salvar_cronograma()`, chame:
```python
texto_crono = _texto_cronograma_para_fts(cr)
# documento_id do cronograma: use o id do DocumentoORM salvo — ou crie um registro
# de documento para o cronograma (tipo=TipoDocumento.CRONOGRAMA) antes de chamar
# salvar_cronograma, para ter o documento_id real.
```

**Atenção — verifique se `salvar_cronograma` já cria um `DocumentoORM`:**
Leia `repositorio.py::salvar_cronograma` — se não criar, adicione antes:
```python
doc_crono = salvar_documento_com_acoes(
    session, projeto_id, nome_arquivo, TipoDocumento.CRONOGRAMA,
    resumo=f"Cronograma: {cr.nome_projeto}", acoes=[]
)
reindexar_documento(engine, doc_crono.id, projeto_id, texto_crono)
```

Se já criar, use o `id` do documento retornado.

**Armadilha:** `reindexar_documento` em `infra/busca.py` recebe `engine`, não `session`.
Verifique a assinatura real antes de chamar — não especule.

---

## PROBLEMA 4 — Chat com consciência de datas

### Causa raiz
O prompt atual do Chat (`core/prompts/chat.py`) não inclui a data de hoje nem
instrui o LLM a interpretar expressões temporais relativas como "próximas 2 semanas"
ou "até data X".

### Solução: enriquecer o contexto do chat com data atual e tarefas estruturadas

**Parte 4A — Modificar o contexto enviado ao chat em `ui/app.py`:**

```python
# Em ui/app.py, no bloco de submit do chat, antes de chamar responder_pergunta():
from datetime import date as _date_type

hoje = _date_type.today()
contexto_projeto = f"Projeto: {cr.nome_projeto if cr else nome_projeto}\n"
contexto_projeto += f"Data de hoje: {hoje.strftime('%d/%m/%Y')}\n"

if cr:
    # Adiciona sumário estruturado do cronograma ao contexto do chat
    contagem_ctx = classificar_tarefas_por_status(cr.tarefas)
    contexto_projeto += f"Status do cronograma: {contagem_ctx}\n"
    
    # Próximas 4 semanas
    limite = hoje + timedelta(weeks=4)
    proximas = [
        t for t in cr.tarefas
        if not t.eh_resumo
        and t.termino is not None
        and hoje <= t.termino <= limite
        and t.percentual_concluido < 100
    ]
    if proximas:
        contexto_projeto += "Atividades nos próximos 30 dias:\n"
        for t in proximas[:10]:  # máx 10 para não estourar contexto
            contexto_projeto += (
                f"- {t.nome}: prevista para {t.termino.strftime('%d/%m/%Y')}, "
                f"{t.percentual_concluido:.0f}% concluída"
                f"{', ATRASADA' if t.atrasada else ''}\n"
            )
```

Adicione `from datetime import timedelta` nos imports de `app.py`.

**Parte 4B — Atualizar o system prompt do chat em `core/prompts/chat.py`:**

Leia o arquivo atual inteiramente. Adicione ao system prompt:

```
Você tem acesso à data de hoje, fornecida em <contexto_projeto>.
Quando o usuário perguntar sobre "próximas X semanas", "até [data]", "esta semana",
"mês que vem" etc., calcule as datas a partir da data de hoje fornecida.
Ao responder sobre atividades por prazo, cite o nome da atividade e a data prevista.
Se os trechos recuperados não cobrem o período perguntado mas o contexto_projeto
contém as atividades diretamente, use o contexto_projeto como fonte secundária
e indique que a informação vem do cronograma estruturado, não de texto da ata.
```

---

## TESTES OBRIGATÓRIOS

**Novos testes em `tests/test_parsers.py`:**
- `test_detectar_layout_ms_project`: texto com "% Expected Task" → retorna "ms_project"
- `test_detectar_layout_dashboard`: texto com "A Iniciar" + "Concluído" + "Resp." → "dashboard_executivo"
- `test_detectar_layout_desconhecido`: texto aleatório → "desconhecido"
- `test_parsear_dashboard_executivo_basico`: texto mínimo com 2 tarefas → Cronograma com tarefas corretas
- `test_parsear_cronograma_vazio_avisa`: cronograma com layout desconhecido → tarefas=[] (sem exceção)

**Novos testes em `tests/test_relatorio.py`:**
- `test_texto_cronograma_para_fts_contem_nomes`: texto gerado contém nomes das tarefas
- `test_texto_cronograma_para_fts_contem_datas`: texto gerado contém datas formatadas em pt-BR
- `test_texto_cronograma_para_fts_exclui_resumos`: linhas `eh_resumo=True` não aparecem no texto

---

## COMMITS SEPARADOS (nesta ordem)

```
fix(parser): detectar_layout + parser Layout B (Dashboard Executivo)
fix(ui): feedback visual quando cronograma retorna vazio
feat(ui): dashboard expandido com 4 seções e gráfico de pizza
feat(infra): indexar texto do cronograma no FTS5
feat(ui/chat): contexto de data e sumário de próximas atividades no chat
fix(prompts): system prompt do chat com consciência de datas
test: testes para detectar_layout, parser Dashboard e texto FTS
chore: plotly em deps + requirements.txt regenerado
```

Push após cada commit.

---

## ARMADILHAS DESTA TASK

- **Layout B sem baseline:** `percentual_esperado=None` para todas as tarefas do Dashboard Executivo. O critério de atraso `TarefaCronograma.atrasada` cai no segundo branch (`termino > termino_baseline`) — mas como `termino_baseline=None`, nenhuma tarefa é marcada atrasada. Isso é correto para Layout B: o status de atraso vem do campo literal "A Iniciar"/"Concluído". Ajuste `_parsear_dashboard_executivo` para marcar como atrasada tarefas cujo `termino` já passou de `date.today()` e `percentual_concluido < 100`.

- **IDs decimais do Layout B:** `id_tarefa: int` no schema. Use `hash(id_str) % 10**9` ou um contador sequencial simples — o que importa é unicidade dentro do projeto, não o valor original.

- **plotly no Streamlit Cloud:** `plotly` já é dependência transitiva do Streamlit — provavelmente já disponível. Confirme com `uv run python -c "import plotly; print(plotly.__version__)"` antes de adicionar ao `pyproject.toml`. Se já estiver, não adicione (evita conflito de versão).

- **`reindexar_documento` vs `indexar`:** leia `infra/busca.py` para confirmar a assinatura exata. Se a função for `indexar(engine, documento_id, projeto_id, texto)`, use essa. Não assuma o nome sem ler.

- **`timedelta` em `app.py`:** importe de `datetime` — `from datetime import date, timedelta`. Não confunda com `datetime.timedelta`.

- **Contexto do chat não pode estourar:** o sumário de próximas atividades tem `[:10]`. Se o projeto tiver 200 tarefas nos próximos 30 dias (improvável mas possível), o contexto explode. O limite de 10 é conservador — mantenha.

---

## VERIFICAÇÃO FINAL

```bash
uv run pytest -q                          # todos os testes, incluindo novos
uv run ruff check src/ tests/
uv run mypy src/pmo_assistant/core/
uv run streamlit run src/pmo_assistant/ui/app.py &
sleep 5 && curl -s http://localhost:8501/_stcore/health
kill %1
```

**Teste manual obrigatório antes de declarar concluído:**
1. Sobe o cronograma do Charqueadas (Layout A) → confirma 4 seções + gráfico de pizza
2. Pergunta no chat: "Quais atividades estão previstas para as próximas 2 semanas?" → deve responder com datas
3. Pergunta no chat: "Quais tarefas estão atrasadas no cronograma?" → deve responder (agora indexado no FTS5)
4. Se tiver o Dashboard da Tripla disponível: sobe → confirma que não mostra 0%

---

## CRITÉRIO DE CONCLUSÃO

Reporte em tabela:
- Layout B detectado e parseado sem retornar 0%: SIM/NÃO/NÃO TESTADO (sem arquivo)
- Aviso visual quando cronograma retorna vazio: SIM/NÃO
- Gráfico de pizza com 4 categorias: SIM/NÃO
- 4 expanders (Concluídas, No Prazo, Atrasadas, Futuras): SIM/NÃO
- Texto do cronograma indexado no FTS5: SIM/NÃO
- Chat responde sobre datas do cronograma: SIM/NÃO
- pytest verde incluindo novos testes: SIM/NÃO
- requirements.txt atualizado se plotly foi adicionado: SIM/NÃO/NÃO NECESSÁRIO
