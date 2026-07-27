# TASK — Redesign Visual ui/app.py

Leia OBRIGATORIAMENTE antes de tocar em qualquer arquivo:
- `CLAUDE.md` (regras críticas, regra de dependência)
- `src/pmo_assistant/ui/app.py` (arquivo alvo — inteiro)
- `.streamlit/config.toml` (tema base já configurado)
- `src/pmo_assistant/infra/db.py` (campos reais do ORM — não invente campos)
- `src/pmo_assistant/core/models.py` (schemas reais — NivelSaude, TarefaCronograma, AcaoExtraida)

Use `/plan` agora. Confirme em 3 frases o que vai mudar e o que NÃO vai mudar antes de editar qualquer linha.

---

## Objetivo

Redesenhar o visual de `src/pmo_assistant/ui/app.py` para ficar próximo ao mockup aprovado pelo usuário, dentro das limitações reais do Streamlit. **Zero alteração em lógica de negócio, imports de core/, infra/ ou testes.**

---

## O que o mockup aprovou (implemente exatamente isso)

### Sidebar
- Ícone SVG de grafo/rede centralizado no topo (desenhe em SVG inline, tema verde escuro)
- "PMO ASSISTANT" em maiúsculas, bold, branco, fonte grande
- "v0.1 — MVP" em cinza claro abaixo
- Linha separadora fina na cor `#40916C`
- Label "Selecionar Projeto Ativo" em branco, bold
- Seletor de projeto nativo do Streamlit (`st.selectbox`) — não substitua por HTML
- Seção "Criar Novo Projeto" com label em branco
- Botão "CRIAR" em amarelo (`#E9C46A`) com texto escuro (`#212529`), maiúsculas, largura total
- Rodapé fixo no bottom: "TCC MBA GESTÃO DE PROJETOS · 2026" em cinza claro, centralizado

### Cards de métricas (aba Cronograma & Saúde)
Substitua os 3 blocos de `st.markdown(HTML)` atuais por uma função reutilizável:

```python
def card_saude(titulo: str, valor: str, subtitulo: str | None, cor_fundo: str, cor_texto: str, icone: str) -> None:
    """Card de métrica com HTML inline. Não usa st.metric — limitação de cor por status."""
```

Regras de cor por nível:
- `NivelSaude.ATRASADO` → fundo `#E63946`, texto `#F8F9FA`, ícone 🔴
- `NivelSaude.EM_RISCO` → fundo `#E9C46A`, texto `#212529`, ícone ⚠️
- `NivelSaude.NO_PRAZO` → fundo `#40916C`, texto `#F8F9FA`, ícone ✅
- `NivelSaude.SEM_DADOS` → fundo `#ADB5BD`, texto `#212529`, ícone —

Card "% Concluído": fundo branco, borda `#ADB5BD`, barra de progresso interna mantida (HTML inline como está hoje).

Card "Tarefas Atrasadas": fundo `#212529` (preto), texto branco, número grande em vermelho se > 0, verde se = 0.

### CSS global
Substitua o bloco `st.markdown(<style>...)` atual pelo CSS abaixo, expandido:

```css
/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    border-bottom: 2px solid #2D6A4F;
    gap: 2rem;
    padding-bottom: 0;
}
.stTabs [aria-selected="true"] {
    color: #1B4332 !important;
    font-weight: 700;
    border-bottom: 3px solid #1B4332;
}
.stTabs [data-baseweb="tab"] {
    font-size: 1rem;
    padding: 0.75rem 0.5rem;
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: #1B4332;
    border-right: 1px solid #2D6A4F;
}
section[data-testid="stSidebar"] * { color: #F8F9FA !important; }
section[data-testid="stSidebar"] .stSelectbox label { font-weight: 600; }

/* Botão primário (Extrair, Analisar) */
.stButton > button[kind="primary"] {
    background-color: #2D6A4F;
    border: none;
    border-radius: 6px;
    font-weight: 600;
    letter-spacing: 0.03em;
    transition: background 0.2s;
}
.stButton > button[kind="primary"]:hover { background-color: #1B4332; }

/* Botão CRIAR na sidebar — amarelo */
section[data-testid="stSidebar"] .stButton > button {
    background-color: #E9C46A !important;
    color: #212529 !important;
    border: none;
    border-radius: 6px;
    font-weight: 700;
    letter-spacing: 0.08em;
    width: 100%;
}
section[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #d4af37 !important;
}

/* File uploader */
[data-testid="stFileUploader"] {
    border: 2px dashed #2D6A4F;
    border-radius: 8px;
    padding: 0.5rem;
    background: #f0f4f0;
}

/* Dataframe — só o contorno (header é canvas, não alcançável por CSS) */
[data-testid="stDataFrame"] {
    border: 1px solid #2D6A4F;
    border-radius: 6px;
}

/* Container geral */
div.block-container { padding-top: 0.75rem; }

/* Título da página */
h1 { color: #1B4332 !important; font-weight: 800; }
```

### Cabeçalho da página
Substitua `st.title` + `st.caption` por:

```python
st.markdown(f"""
<div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem;">
    <span style="font-size:2rem;">📊</span>
    <div>
        <h1 style="margin:0; color:{VERDE_ESCURO}; font-size:1.8rem; font-weight:800;">
            PMO Assistant
        </h1>
        <p style="margin:0; color:{CINZA_MEDIO}; font-size:0.9rem;">
            Extração de ações · Análise de cronograma · Chat do projeto
        </p>
    </div>
</div>
""", unsafe_allow_html=True)
```

---

## O que NÃO implementar (fora de escopo — não invente)

- Gráfico horizontal por WBS: `TarefaORM` não tem campo de fase/WBS. O `st.bar_chart` vertical de contagem por status permanece.
- Coluna "Responsável" na tabela de tarefas atrasadas: campo não existe em `TarefaORM`.
- Coluna "Atraso (Dias)": não existe no ORM. Não calcule com lógica nova.
- Qualquer import novo de biblioteca (plotly, altair, etc.).
- Qualquer mudança em `core/`, `infra/`, `tests/`.

---

## Armadilhas desta task

- `st.dataframe` usa canvas — **não tente colorir header ou células via CSS**. Prefixo emoji no valor da string é o único caminho (já implementado com `cor_status`).
- `st.chat_input` deve ficar **diretamente dentro de `with aba_chat:`**, não dentro de `with col:`.
- O botão "CRIAR" e o botão "Extrair ações" são elementos diferentes — o CSS da sidebar com `section[data-testid="stSidebar"] .stButton` afeta só botões dentro da sidebar. Confirme que o seletor CSS não vaza para os botões primários do conteúdo principal.
- Variáveis de cor Python (`VERDE_ESCURO`, `AMARELO`, etc.) já existem no topo do arquivo — use-as nas f-strings HTML. Não hardcode hex novo sem definir a variável.
- `f"""..."""` com CSS dentro de `st.markdown`: chaves CSS precisam de escape duplo `{{` e `}}`.

---

## Critério de conclusão

1. `uv run streamlit run src/pmo_assistant/ui/app.py` sobe sem erro
2. `uv run pytest -q` verde (nenhum teste tocado)
3. `uv run ruff check src/pmo_assistant/ui/` limpo
4. Sidebar tem ícone SVG, título, seletor, botão amarelo e rodapé
5. Cards de saúde mudam de cor conforme `NivelSaude` (teste visual: force `NivelSaude.ATRASADO` temporariamente e confirme vermelho)
6. Nenhum campo inventado que não existe no ORM
