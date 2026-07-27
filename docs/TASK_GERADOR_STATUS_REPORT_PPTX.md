# TASK — Gerador de Status Report em PPTX
# Salve em: pmo-assistant/docs/TASK_GERADOR_STATUS_REPORT_PPTX.md
# No terminal: `claude` → cole @docs/TASK_GERADOR_STATUS_REPORT_PPTX.md

---

## LEITURA OBRIGATÓRIA ANTES DE QUALQUER CÓDIGO

Leia integralmente, nesta ordem:

1. `CLAUDE.md` — regras críticas e regra de dependência (`ui/ → core/`, `ui/ → infra/`, `core/` nunca importa `infra/`)
2. `src/pmo_assistant/core/models.py` — schemas `Cronograma`, `TarefaCronograma`, `Projeto`
3. `src/pmo_assistant/infra/repositorio.py` — função `salvar_cronograma` (**leia com atenção — ver Achado Crítico abaixo**)
4. `src/pmo_assistant/core/saude.py` — padrão de função pura já estabelecido
5. `src/pmo_assistant/ui/app.py` — bloco `with aba_crono:` completo
6. `pyproject.toml` — dependências atuais

Use `/plan` e confirme em 5 frases antes de codificar: (a) de onde o PPTX vai extrair os dados — sessão ou banco, e por quê; (b) por que os 3 arquivos novos ficam onde ficam; (c) qual biblioteca de geração e por que não a alternativa; (d) quais campos do Netcon-style NÃO existem no schema e serão omitidos; (e) os 5 slides do MVP.

---

## CONTEXTO DE NEGÓCIO

O usuário (PMO/gestor de projetos) hoje monta manualmente um Status Report em PowerPoint para cada cliente, toda semana ou mês, copiando dados do cronograma do MS Project para slides. Essa task automatiza isso: o cronograma já é parseado pelo `parsear_cronograma()` existente — o objetivo é gerar o PPTX a partir do mesmo objeto `Cronograma`, sem retrabalho de digitação.

O usuário forneceu como referência de estilo um Status Report real de um fornecedor (Netcon Americas, projeto Grantel-Axia Sul — Ampliação SE Charqueadas). A estrutura visual (cards de resumo, gráfico de status, tabelas de atividades, pontos de atenção) deve ser replicada. **A marca do fornecedor (logo, nome "Netcon") NÃO deve ser hardcoded** — este é um gerador genérico para qualquer projeto/cliente cadastrado no sistema.

---

## ACHADO CRÍTICO — leia antes de decidir a fonte de dados

`repositorio.py::salvar_cronograma` filtra `if not t.eh_resumo` antes de persistir em `TarefaORM`:

```python
tarefas_orm = [
    TarefaORM(...)
    for t in tarefas
    if not t.eh_resumo
]
```

**Isso significa que o banco (`TarefaORM`) nunca contém a linha-resumo raiz (`id_tarefa == 1`) nem as linhas de fase (PLANEJAMENTO, EXECUÇÃO etc.).** Essas linhas-resumo são exatamente onde estão os 5 valores do card "Resumo Geral" do modelo Netcon: `percentual_esperado` geral, `inicio_baseline`/`termino_baseline` do projeto todo, e `termino` (impacto).

**Consequência prática: o PPTX DEVE ser gerado a partir de `st.session_state.cronograma`** (o objeto `Cronograma` completo, em memória, logo após o parse) — **nunca** reconstruído via `listar_tarefas_por_projeto()` do banco, que perderia os dados de resumo geral silenciosamente.

Isso implica: o botão "Gerar Status Report" fica na aba Cronograma, na mesma sessão em que o PDF foi analisado — não é possível gerar o relatório de um cronograma antigo sem reenviar o PDF. Documente essa limitação no docstring da função e no manual do usuário (fora de escopo desta task alterar o manual).

---

## MAPEAMENTO DE DADOS — Netcon-style → PMO Assistente

Verificado contra o cronograma real do projeto Charqueadas (linha `id_tarefa == 1`, dados reais extraídos: 94% concluído real, 99% esperado, baseline 03/12/25 → 09/07/26, término com impacto 11/08/26):

| Elemento do slide Netcon | Fonte no `Cronograma` | Observação |
|---|---|---|
| % Concluído Previsto | `tarefa_raiz.percentual_esperado` | `tarefa_raiz` = `next(t for t in cr.tarefas if t.id_tarefa == 1)` |
| % Concluído Real | `tarefa_raiz.percentual_concluido` | idêntico a `Cronograma.percentual_geral` |
| Início Linha de Base | `tarefa_raiz.inicio_baseline` | |
| Término Linha de Base | `tarefa_raiz.termino_baseline` | |
| Término (Impacto) | `tarefa_raiz.termino` | término atual/reprogramado, pode diferir do baseline |
| Status das tarefas (gráfico) | Classificação sobre `cr.tarefas` filtrado por `not eh_resumo` | ver lógica abaixo |
| Atividades Realizadas | tarefas com `percentual_concluido >= 100` | colunas: nome, `termino_baseline` (prevista), `termino_real` (real) |
| Próximas Atividades | tarefas com `percentual_concluido < 100` e `not atrasada` | colunas: nome, `termino_baseline` (prevista), `termino` (reprogramação) |
| Pontos de Atenção | tarefas com `atrasada == True` | colunas: nome, `termino_baseline`, `termino` |
| Responsável (coluna da tabela) | **NÃO EXISTE** | `TarefaCronograma` não tem campo `responsavel`. **Omita a coluna.** Não invente. |
| Curva S (% acumulado por mês) | **Fora de escopo do MVP** | ver Fase Opcional no final |

---

## DECISÃO DE ARQUITETURA — bibliotecas

**Use `python-pptx`.** Justificativa comparativa obrigatória por CLAUDE.md:

- **`python-pptx` vs. renderizar HTML/CSS e converter com LibreOffice (`soffice`):** o Streamlit Cloud (ambiente de produção deste projeto — ver `CLAUDE.md`) **não tem `soffice` instalado**. Uma abordagem baseada em LibreOffice funciona local e quebra silenciosamente em produção. `python-pptx` é pure Python, zero binário externo, funciona idêntico local e no Streamlit Cloud.
- **`python-pptx` vs. gerar imagem estática (matplotlib → PNG → inserir no slide):** o cliente final recebe o arquivo `.pptx` para editar — um gráfico nativo (`add_chart`) é editável no PowerPoint; uma imagem não é. Use gráficos nativos do python-pptx (`XL_CHART_TYPE`), não `matplotlib`.

Adicione ao `pyproject.toml`:
```toml
dependencies = [
    # ... existentes ...
    "python-pptx>=1.0.0",
]
```

**Armadilha de deploy:** depois de adicionar a dependência, regenere `requirements.txt` (o Streamlit Cloud usa pip, não uv):
```bash
uv sync
uv export --no-hashes --format requirements-txt > requirements.txt
```
Sem isso o próximo deploy quebra com `ModuleNotFoundError: No module named 'pptx'` — exatamente o tipo de falha silenciosa já visto neste projeto com o `requirements.txt` desatualizado.

---

## ARQUITETURA DE CÓDIGO — respeite a separação core/infra

### Novo arquivo: `src/pmo_assistant/core/relatorio.py` (puro, zero I/O, testável sem banco/arquivo)

```python
"""Lógica de agregação para relatórios. Zero I/O — testável sem banco/arquivo.

Consome Cronograma (objeto em memória), nunca toca infra/.
"""
from __future__ import annotations
from pmo_assistant.core.models import Cronograma, TarefaCronograma


def tarefa_raiz(cr: Cronograma) -> TarefaCronograma | None:
    """Linha-resumo do projeto (id_tarefa == 1). Contém os agregados gerais
    que NÃO existem em nenhuma tarefa de folha — ver Achado Crítico no
    TASK que originou este módulo. Pode ser None se o PDF não tiver
    linha-resumo raiz; chamador deve tratar com fallback gracioso.
    """
    return next((t for t in cr.tarefas if t.id_tarefa == 1), None)


def classificar_tarefas_por_status(tarefas: list[TarefaCronograma]) -> dict[str, int]:
    """Classifica tarefas de folha (eh_resumo=False) em 4 categorias.

    Concluída: percentual_concluido >= 100 (implica atrasada=False, ver
        TarefaCronograma.atrasada — uma tarefa 100% nunca é marcada atrasada).
    Atrasada: atrasada is True (usa o computed_field já existente — não
        reimplemente a lógica de atraso aqui).
    Futura: ainda não iniciada (inicio_real is None) e não atrasada.
    No Prazo: tudo o mais — em andamento, dentro do previsto.
    """
    folhas = [t for t in tarefas if not t.eh_resumo]
    contagem = {"Concluída": 0, "No Prazo": 0, "Atrasada": 0, "Tarefa Futura": 0}
    for t in folhas:
        if t.percentual_concluido >= 100:
            contagem["Concluída"] += 1
        elif t.atrasada:
            contagem["Atrasada"] += 1
        elif t.inicio_real is None:
            contagem["Tarefa Futura"] += 1
        else:
            contagem["No Prazo"] += 1
    return contagem


def atividades_realizadas(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [t for t in tarefas if not t.eh_resumo and t.percentual_concluido >= 100]


def proximas_atividades(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [
        t for t in tarefas
        if not t.eh_resumo and t.percentual_concluido < 100 and not t.atrasada
    ]


def pontos_de_atencao(tarefas: list[TarefaCronograma]) -> list[TarefaCronograma]:
    return [t for t in tarefas if not t.eh_resumo and t.atrasada]
```

Ajuste nomes/assinaturas se ao ler `models.py` encontrar diferença do que está documentado acima — o código real é a fonte de verdade, este é um rascunho de referência.

### Novo arquivo: `src/pmo_assistant/infra/relatorio_pptx.py` (I/O — gera bytes do arquivo)

Função principal:
```python
def gerar_status_report_pptx(
    cronograma: Cronograma,
    cliente: str | None,
    gerado_em: date,
) -> bytes:
    """Gera o PPTX em memória (BytesIO), retorna bytes prontos para download.
    Não escreve em disco — Streamlit Cloud tem filesystem efêmero (ver
    CLAUDE.md, Armadilhas Conhecidas)."""
```

Use `io.BytesIO()` + `prs.save(buffer)` + `buffer.getvalue()`. **Não escreva em `/tmp` ou caminho local** — o retorno vai direto para `st.download_button(data=...)`.

---

## ESPECIFICAÇÃO VISUAL — paleta própria do relatório

**Não reutilize as constantes `VERDE_*` de `ui/app.py`.** O relatório é um deliverable para o cliente final, com identidade visual corporativa própria — independente do tema verde do PMO Assistente em si. Defina no topo de `relatorio_pptx.py`:

```python
NAVY = RGBColor(0x0B, 0x25, 0x45)        # header, título
TEAL = RGBColor(0x14, 0xB8, 0xA6)        # underline/gradiente, destaque
CINZA_CLARO = RGBColor(0xF4, 0xF6, 0xF8) # fundo de card
CINZA_LINHA = RGBColor(0xE8, 0xEC, 0xEF) # linha alternada de tabela
BRANCO = RGBColor(0xFF, 0xFF, 0xFF)
TEXTO_ESCURO = RGBColor(0x1B, 0x1F, 0x23)
VERMELHO_ATRASO = RGBColor(0xE6, 0x39, 0x46)  # mesmo vermelho do app — consistência de semântica "atraso"
AMARELO_ALERTA = RGBColor(0xF2, 0xC9, 0x4C)
```

Slide: 16:9 widescreen. `prs.slide_width = Inches(13.333)`, `prs.slide_height = Inches(7.5)`. Use layout em branco (índice 6 do template padrão) e posicione shapes manualmente — não use placeholders de layout, eles restringem o posicionamento.

Fonte: Calibri (padrão, disponível em qualquer instalação do PowerPoint). Título de slide: 28pt bold branco sobre NAVY. Underline: retângulo fino TEAL, 0.08in de altura, logo abaixo do título.

### Slide 1 — Capa
- Fundo NAVY
- Título: nome do projeto, 36pt bold branco, centralizado
- Se `cliente` não for None: subtítulo "Cliente: {cliente}", 18pt, TEAL
- "Status Report — {gerado_em.strftime('%d/%m/%Y')}", 20pt branco
- Rodapé: "Gerado por PMO Assistente", 10pt cinza claro

### Slide 2 — Resumo Geral
- Header NAVY com underline TEAL, título "Resumo Geral"
- 5 cards em linha (usar `tarefa_raiz()`; se None, cards mostram "N/D"):
  - Cada card: retângulo CINZA_CLARO, label 10pt bold uppercase NAVY no topo, valor 22pt bold TEXTO_ESCURO abaixo
  - Cards: "% Concluído Previsto", "% Concluído Real", "Início Linha de Base", "Término Linha de Base", "Término (Impacto)"
  - Datas formatadas `%d/%m/%Y`; percentuais com `%.0f%%`; `None` vira "N/D"
- Abaixo dos cards: gráfico de barras nativo (`XL_CHART_TYPE.COLUMN_CLUSTERED`) com as 4 categorias de `classificar_tarefas_por_status()`. Cor das barras: Concluída=TEAL, No Prazo=NAVY, Atrasada=VERMELHO_ATRASO, Tarefa Futura=CINZA_LINHA.

### Slide 3 — Atividades Realizadas
- Header padrão. Se `atividades_realizadas()` vazio: texto centralizado "Nenhuma atividade concluída neste período."
- Senão: tabela nativa (`shapes.add_table`) com header NAVY/branco, linhas alternando BRANCO/CINZA_LINHA. Colunas: Atividade | Entrega Prevista | Entrega Real.
- Se a lista tiver mais de 12 itens, mostre os 12 mais recentes por `termino_real` e adicione nota "+N atividades adicionais não exibidas" — não deixe o slide estourar a página.

### Slide 4 — Próximas Atividades
- Mesma estrutura da 3, usando `proximas_atividades()`. Colunas: Atividade | Entrega Prevista | Nova Previsão.
- Vazio: "Nenhuma atividade pendente registrada."

### Slide 5 — Pontos de Atenção
- Mesma estrutura, usando `pontos_de_atencao()`. Linhas com texto em VERMELHO_ATRASO (task atrasada = alerta visual).
- Vazio: mostrar em TEAL "Nenhuma tarefa atrasada — projeto dentro do previsto." (mensagem positiva, não genérica)
- Colunas: Atividade | Prevista | Atual

---

## INTEGRAÇÃO NA UI

Em `ui/app.py`, dentro de `with aba_crono:`, no bloco `if cr:` (onde o dashboard já é renderizado), adicione — **depois** da lista de tarefas atrasadas existente:

```python
st.divider()
st.subheader("Status Report para o Cliente")
if st.button("Gerar Status Report (PPTX)", type="primary"):
    with st.spinner("Gerando apresentação..."):
        projeto_atual = next(
            (p for p in listar_projetos(session) if p.id == projeto_id_selecionado), None
        )
        cliente = projeto_atual.cliente if projeto_atual else None
        pptx_bytes = gerar_status_report_pptx(cr, cliente, date.today())
    st.download_button(
        "Baixar apresentação",
        data=pptx_bytes,
        file_name=f"status_report_{_slug(cr.nome_projeto)}.pptx",
        mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
    )
```

Adicione um helper `_slug(texto: str) -> str` no topo de `app.py` (regex simples: minúsculas, espaços viram `_`, remove tudo que não for `[a-z0-9_]`). Nome de projeto com acentos/espaços/parênteses (ex: "Charqueadas TLC — Eletrosul (Deal 5792)") não pode virar nome de arquivo inválido.

**Não** re-analise o cronograma nem chame `parsear_cronograma` de novo — use o `cr` que já está em `st.session_state.cronograma`, conforme o Achado Crítico acima.

---

## TESTES OBRIGATÓRIOS

`tests/test_relatorio.py` — puro, sem fakes de I/O, cobrindo `core/relatorio.py`:
- `classificar_tarefas_por_status`: fixture com tarefas cobrindo as 4 categorias + uma linha `eh_resumo=True` que **não deve** ser contada
- `tarefa_raiz`: encontra `id_tarefa == 1`; retorna `None` se ausente
- `atividades_realizadas` / `proximas_atividades` / `pontos_de_atencao`: casos de borda com listas vazias

`tests/test_relatorio_pptx.py` — smoke test de `infra/relatorio_pptx.py`:
- Gera um PPTX com um `Cronograma` fake pequeno (3-4 tarefas)
- Reabre os bytes com `Presentation(io.BytesIO(pptx_bytes))` e confirma `len(prs.slides) == 5`
- Testa também o caso `tarefa_raiz() is None` (cronograma sem linha resumo) — não deve lançar exceção, cards devem mostrar "N/D"
- Testa listas vazias (nenhuma atividade realizada/próxima/atrasada) — não deve lançar exceção

---

## ARMADILHAS CONHECIDAS

- **`add_table` do python-pptx não redimensiona linhas automaticamente para texto longo** — trunque nomes de tarefa acima de ~80 caracteres com reticências antes de inserir na célula, ou o texto vaza da tabela.
- **`XL_CHART_TYPE.COLUMN_CLUSTERED` com todas as categorias em zero** (cronograma sem nenhuma tarefa de folha) quebra a renderização do gráfico — se `sum(contagem.values()) == 0`, pule o gráfico e mostre texto "Sem dados de tarefas para exibir."
- **Datas `None` formatadas direto com `.strftime()` lançam `AttributeError`** — sempre `data.strftime(...) if data else "N/D"`.
- **`RGBColor` espera inteiros, não strings hex** — `RGBColor(0x0B, 0x25, 0x45)`, não `RGBColor("0B2545")`.
- **Nome de arquivo do `download_button`** precisa do slug — caracteres como `/`, `:`, `—` quebram o download em alguns browsers.

---

## O QUE NÃO FAZER

- Não toque `core/models.py`, `infra/db.py` ou `alembic/` — nenhum campo novo, nenhuma migration.
- Não invente coluna "Responsável" — o campo não existe.
- Não implemente a curva S de percentual acumulado — fica para uma sessão futura (ver Fase Opcional).
- Não escreva o PPTX em disco — sempre em memória (`BytesIO`).
- Não hardcode "Netcon" ou qualquer nome de fornecedor/cliente específico no template.

---

## FASE OPCIONAL — não implementar agora, só documentar como próximo passo

Curva S (percentual acumulado por mês, como no slide 2 do modelo Netcon): seria calculável agregando `termino_real` das tarefas de folha por mês/ano e dividindo pelo total, sem precisar de campo novo no schema — mas exige lógica de bucketing por data e extrapolação para tarefas futuras via `termino_baseline`. Escopo maior, fica de fora deste MVP. Registre isso como comentário `# TODO` no topo de `relatorio_pptx.py`, uma linha, sem implementar.

---

## VERIFICAÇÃO FINAL

```bash
uv run pytest -q                                    # todos os testes, incluindo os novos
uv run ruff check src/ tests/
uv run mypy src/pmo_assistant/core/                 # inclui o novo relatorio.py
uv run streamlit run src/pmo_assistant/ui/app.py &
sleep 5 && curl -s http://localhost:8501/_stcore/health
kill %1
```

Teste manual: suba um cronograma real, clique "Gerar Status Report (PPTX)", baixe o arquivo, abra no PowerPoint/LibreOffice e confirme visualmente os 5 slides antes de considerar concluído.

---

## COMMITS SEPARADOS

```
feat(core): relatorio.py — classificação e agregação puras para status report
feat: adicionar python-pptx às dependências + requirements.txt
feat(infra): relatorio_pptx.py — geração de Status Report em PPTX
feat(ui): botão "Gerar Status Report" na aba Cronograma
test: test_relatorio.py e test_relatorio_pptx.py
```

Cada commit `git push` individual, não agrupar.

---

## CRITÉRIO DE CONCLUSÃO

Reporte em tabela:
- Achado crítico (fonte de dados = session_state, não banco) respeitado: SIM/NÃO
- Coluna "Responsável" omitida (não inventada): SIM/NÃO
- pytest verde incluindo os novos testes: SIM/NÃO
- mypy limpo em core/ incluindo relatorio.py: SIM/NÃO
- requirements.txt regenerado com python-pptx: SIM/NÃO
- PPTX gerado manualmente e aberto com sucesso, 5 slides confirmados: SIM/NÃO

Não declare concluído sem o teste manual de abrir o arquivo gerado.
