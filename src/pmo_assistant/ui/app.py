"""UI Streamlit do PMO Assistant.

Esta camada NÃO contém lógica de negócio — só orquestra core/ e infra/ e renderiza.
Rodar: uv run streamlit run src/pmo_assistant/ui/app.py
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING

import streamlit as st
from alembic import command as alembic_command
from alembic.config import Config
from dotenv import load_dotenv
from loguru import logger
from sqlalchemy import select

if TYPE_CHECKING:
    from sqlalchemy import Engine
    from sqlalchemy.orm import Session, sessionmaker

load_dotenv()

from pmo_assistant.core.chat import responder_pergunta  # noqa: E402
from pmo_assistant.core.extractors.acoes import extrair_acoes  # noqa: E402
from pmo_assistant.core.models import (  # noqa: E402
    AcaoExtraida,
    Cronograma,
    NivelSaude,
    StatusAcao,
    TarefaCronograma,
    TipoDocumento,
)
from pmo_assistant.core.parsers.cronograma import parsear_cronograma  # noqa: E402
from pmo_assistant.core.saude import avaliar_saude  # noqa: E402
from pmo_assistant.infra.busca import buscar, reindexar_documento  # noqa: E402
from pmo_assistant.infra.db import (  # noqa: E402
    AcaoORM,
    DocumentoORM,
    TarefaORM,
    criar_engine,
    criar_session_factory,
    inicializar_schema,
)
from pmo_assistant.infra.docs import DocumentoIlegivelError, ler_documento  # noqa: E402
from pmo_assistant.infra.llm import LLMClient  # noqa: E402
from pmo_assistant.infra.relatorio_pptx import gerar_status_report_pptx  # noqa: E402
from pmo_assistant.infra.repositorio import (  # noqa: E402
    listar_acoes_por_projeto,
    listar_projetos,
    listar_tarefas_por_projeto,
    salvar_cronograma,
    salvar_documento_com_acoes,
    salvar_projeto,
)

st.set_page_config(
    page_title="PMO Assistente", page_icon="📊", layout="wide", initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Paleta e tema (ver .streamlit/config.toml para as cores base do Streamlit)
# ---------------------------------------------------------------------------
VERDE_ESCURO = "#1B4332"
VERDE_MEDIO = "#2D6A4F"
VERDE_CLARO = "#40916C"
VERDE_FUNDO_SUAVE = "#f0f4f0"
AMARELO = "#E9C46A"
AMARELO_ESCURO = "#d4af37"
VERMELHO = "#E63946"
AZUL = "#4361EE"
CINZA_ESCURO = "#212529"
CINZA_MEDIO = "#495057"
CINZA_CLARO = "#ADB5BD"
BRANCO = "#F8F9FA"
PCT_COMPLETO = 100.0

# NOTE: o header do st.dataframe é desenhado em <canvas> (glide-data-grid), não em
# elementos DOM — não é possível colorir o header via CSS injetado. Aplicamos um
# contorno/realce como alternativa mais próxima e documentamos a limitação no PR.
st.markdown(
    f"""
    <style>
    div.block-container {{ padding-top: 2.5rem; }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{
        border-bottom: 2px solid {VERDE_MEDIO};
        gap: 2rem;
        padding-bottom: 0;
    }}
    .stTabs [aria-selected="true"] {{
        color: {VERDE_ESCURO} !important;
        font-weight: 700;
        border-bottom: 3px solid {VERDE_ESCURO};
    }}
    .stTabs [data-baseweb="tab"] {{
        font-size: 1rem;
        padding: 0.75rem 0.5rem;
    }}

    /* Sidebar */
    section[data-testid="stSidebar"] {{
        background: {VERDE_ESCURO};
        border-right: 1px solid {VERDE_MEDIO};
    }}
    section[data-testid="stSidebar"] * {{
        color: {BRANCO} !important;
    }}
    /* Texto digitado/selecionado em inputs e selects da sidebar fica sobre fundo
       claro — o override acima deixava a escrita branca sobre fundo branco
       (invisível). O select do BaseWeb aninha o texto 2 níveis dentro do
       control, por isso o wildcard (não só `> div`) para garantir que vence
       o `*` acima em qualquer profundidade. */
    section[data-testid="stSidebar"] input {{
        color: {CINZA_ESCURO} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] * {{
        color: {CINZA_ESCURO} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox div[data-baseweb="select"] > div {{
        background-color: {BRANCO} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox svg {{
        fill: {CINZA_ESCURO} !important;
    }}
    section[data-testid="stSidebar"] .stSelectbox label {{
        font-weight: 600;
    }}
    /* st.divider() da sidebar — sem isso o <hr> fica cinza padrão do tema. */
    section[data-testid="stSidebar"] hr {{
        border-color: {VERDE_CLARO} !important;
        opacity: 1;
    }}

    /* Botão primário (Extrair, Analisar) */
    .stButton > button[kind="primary"] {{
        background-color: {VERDE_MEDIO};
        border: none;
        border-radius: 6px;
        font-weight: 600;
        letter-spacing: 0.03em;
        transition: background 0.2s;
    }}
    .stButton > button[kind="primary"]:hover {{
        background-color: {VERDE_ESCURO};
    }}

    /* Botão CRIAR na sidebar — amarelo */
    section[data-testid="stSidebar"] .stButton > button {{
        background-color: {AMARELO} !important;
        color: {CINZA_ESCURO} !important;
        border: none;
        border-radius: 6px;
        font-weight: 700;
        letter-spacing: 0.08em;
        width: 100% !important;
    }}
    section[data-testid="stSidebar"] .stButton > button:hover {{
        background-color: {AMARELO_ESCURO} !important;
    }}

    /* File uploader */
    [data-testid="stFileUploader"] {{
        border: 2px dashed {VERDE_MEDIO};
        border-radius: 8px;
        padding: 0.5rem;
        background: {VERDE_FUNDO_SUAVE};
    }}

    /* Dataframe — só o contorno (header é canvas, não alcançável por CSS) */
    [data-testid="stDataFrame"] {{
        border: 1px solid {VERDE_MEDIO};
        border-radius: 6px;
    }}

    h1 {{ color: {VERDE_ESCURO} !important; font-weight: 800; }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div style="display:flex; align-items:center; gap:1rem; margin-bottom:0.5rem;">
        <span style="font-size:2rem;">📊</span>
        <div>
            <h1 style="margin:0; color:{VERDE_ESCURO}; font-size:1.8rem; font-weight:800;">
                PMO Assistente
            </h1>
            <p style="margin:0; color:{CINZA_MEDIO}; font-size:0.9rem;">
                Extração de ações · Análise de cronograma · Chat do projeto
            </p>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def _llm() -> LLMClient:
    return LLMClient()


@st.cache_resource
def _engine() -> Engine:
    eng = criar_engine()
    inicializar_schema(eng)
    return eng


@st.cache_resource
def _rodar_migrations() -> None:
    """Roda as migrations Alembic no boot — Streamlit Cloud sobe com banco vazio,
    sem isso a tabela virtual documentos_fts nunca existe (não é criada por
    inicializar_schema/metadata, só via migration).

    @st.cache_resource garante que roda uma vez por processo, não a cada rerun.
    """
    cfg = Config("alembic.ini")
    alembic_command.upgrade(cfg, "head")


_rodar_migrations()


@st.cache_resource
def _session_factory() -> sessionmaker[Session]:
    return criar_session_factory(_engine())


@st.cache_resource
def _reconciliar_indice_fts() -> None:
    """Reindexa no FTS5 qualquer documento com conteudo_bruto ainda não indexado.

    Sem custo de API (não há embeddings) — pode rodar a cada boot do processo.
    @st.cache_resource garante que roda uma vez por processo, não a cada rerun.
    """
    with _session_factory()() as sess:
        docs = sess.execute(
            select(DocumentoORM).where(DocumentoORM.conteudo_bruto.isnot(None))
        ).scalars().all()
        for doc in docs:
            reindexar_documento(_engine(), doc.id, doc.projeto_id, doc.conteudo_bruto)


def _salvar_tmp(arquivo) -> Path:
    with NamedTemporaryFile(delete=False, suffix=Path(arquivo.name).suffix) as tmp:
        tmp.write(arquivo.read())
        return Path(tmp.name)


def _slug(texto: str) -> str:
    """Nome de projeto com acentos/espaços/parênteses vira nome de arquivo seguro."""
    texto = texto.lower().strip()
    texto = re.sub(r"\s+", "_", texto)
    return re.sub(r"[^a-z0-9_]", "", texto)


def _acao_orm_para_pydantic(acao_orm: AcaoORM) -> AcaoExtraida:
    return AcaoExtraida(
        descricao=acao_orm.descricao,
        responsavel=acao_orm.responsavel,
        prazo=acao_orm.prazo,
        status=StatusAcao(acao_orm.status),
        contexto_origem=acao_orm.contexto_origem,
        confianca=acao_orm.confianca,
    )


def _tarefa_orm_para_pydantic(tarefa_orm: TarefaORM) -> TarefaCronograma:
    return TarefaCronograma(
        id_tarefa=tarefa_orm.id_tarefa,
        nome=tarefa_orm.nome,
        percentual_concluido=tarefa_orm.percentual_concluido,
        percentual_esperado=tarefa_orm.percentual_esperado,
        termino_baseline=tarefa_orm.termino_baseline,
        termino=tarefa_orm.termino,
    )


def card_saude(
    titulo: str, valor: str, subtitulo: str | None, cor_fundo: str, cor_texto: str, icone: str
) -> None:
    """Card de métrica com HTML inline. Não usa st.metric — limitação de cor por status.

    `valor` pode conter HTML próprio (ex.: um <span style="color:..."> embutido) para
    colorir só parte do conteúdo sem depender de um segundo `cor_texto`.
    """
    subtitulo_html = (
        f'<div style="font-size:0.8rem; margin-top:0.3rem;">{subtitulo}</div>'
        if subtitulo
        else ""
    )
    st.markdown(
        f"""
        <div style="background:{cor_fundo}; color:{cor_texto}; border-radius:8px;
                    padding:1.2rem; text-align:center;">
            <div style="font-size:0.85rem; text-transform:uppercase; font-weight:600;">
                {(icone + " " + titulo) if icone else titulo}
            </div>
            <div style="font-size:1.8rem; font-weight:700; margin-top:0.3rem;">{valor}</div>
            {subtitulo_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _carregar_projeto(projeto_id: int, nome_projeto: str) -> None:
    """Recarrega ações e cronograma persistidos do projeto selecionado."""
    with _session_factory()() as sess:
        acoes_orm = listar_acoes_por_projeto(sess, projeto_id)
        st.session_state.acoes = [
            (a.documento.nome_arquivo, _acao_orm_para_pydantic(a)) for a in acoes_orm
        ]
        tarefas_orm = listar_tarefas_por_projeto(sess, projeto_id)
    st.session_state.cronograma = (
        Cronograma(
            projeto_id=projeto_id,
            nome_projeto=nome_projeto,
            tarefas=[_tarefa_orm_para_pydantic(t) for t in tarefas_orm],
        )
        if tarefas_orm
        else None
    )


for chave in ("acoes", "cronograma"):
    st.session_state.setdefault(chave, [] if chave == "acoes" else None)
st.session_state.setdefault("projeto_id_carregado", None)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        f"""
        <div style="text-align:center; color:{BRANCO};">
            <svg width="40" height="40" viewBox="0 0 48 48" fill="none"
                 xmlns="http://www.w3.org/2000/svg" style="margin:0 auto;">
                <line x1="24" y1="10" x2="10" y2="34" stroke="{VERDE_CLARO}" stroke-width="2"/>
                <line x1="24" y1="10" x2="38" y2="34" stroke="{VERDE_CLARO}" stroke-width="2"/>
                <line x1="10" y1="34" x2="38" y2="34" stroke="{VERDE_CLARO}" stroke-width="2"/>
                <circle cx="24" cy="10" r="5" fill="{VERDE_CLARO}"/>
                <circle cx="10" cy="34" r="5" fill="{VERDE_CLARO}"/>
                <circle cx="38" cy="34" r="5" fill="{VERDE_CLARO}"/>
            </svg>
            <h2 style="color:{BRANCO}; margin:0.5rem 0 0 0; text-transform:uppercase;
                       font-weight:800;">
                PMO Assistente
            </h2>
            <small style="color:{CINZA_CLARO};">v0.1 — MVP</small>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    session_factory = _session_factory()
    with session_factory() as sess:
        projetos_por_nome = {p.nome: p.id for p in listar_projetos(sess)}

    projeto_nome_selecionado: str | None = None
    projeto_id_selecionado: int | None = None
    if projetos_por_nome:
        projeto_nome_selecionado = st.selectbox(
            "Selecionar Projeto Ativo", list(projetos_por_nome.keys())
        )
        projeto_id_selecionado = projetos_por_nome[projeto_nome_selecionado]
    else:
        st.markdown(
            f'<p style="color:{CINZA_CLARO}; font-style:italic; font-size:0.85rem; '
            f'margin:0.5rem 0;">Nenhum projeto cadastrado. Crie um abaixo.</p>',
            unsafe_allow_html=True,
        )

    st.markdown("**Criar Novo Projeto**")
    novo_projeto = st.text_input("Nome do novo projeto", label_visibility="collapsed")
    if st.button("CRIAR") and novo_projeto.strip():
        with session_factory() as sess:
            salvar_projeto(sess, nome=novo_projeto.strip())
        st.success(f"Projeto '{novo_projeto.strip()}' criado.")
        st.rerun()

    st.divider()
    # Rodapé permanece no fim do fluxo da sidebar em vez de position:fixed — a
    # sidebar é uma coluna flex com conteúdo dinâmico (lista de projetos varia),
    # fixed pode sobrepor conteúdo ou cortar em telas pequenas.
    st.markdown(
        f"""
        <p style="text-align:center; color:{CINZA_CLARO}; font-size:0.75rem;">
            TCC MBA GESTÃO DE PROJETOS · 2026
        </p>
        """,
        unsafe_allow_html=True,
    )

if (
    projeto_id_selecionado is not None
    and projeto_id_selecionado != st.session_state.projeto_id_carregado
):
    _carregar_projeto(projeto_id_selecionado, projeto_nome_selecionado)
    st.session_state.projeto_id_carregado = projeto_id_selecionado

_reconciliar_indice_fts()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------
aba_acoes, aba_crono, aba_chat = st.tabs(
    ["📋 Ações de Atas", "📊 Cronograma & Saúde", "💬 Chat do Projeto"]
)

with aba_acoes:
    c1, c2 = st.columns([3, 1])
    arquivo = c1.file_uploader("Ata ou Status Report (PDF/DOCX)", type=["pdf", "docx"])
    tipo = c2.selectbox(
        "Tipo", [t.value for t in TipoDocumento if t.value != "cronograma"], index=0
    )
    if arquivo and st.button("Extrair ações", type="primary"):
        try:
            conteudo = ler_documento(_salvar_tmp(arquivo))
            with st.spinner("Extraindo ações via LLM..."):
                res = extrair_acoes(conteudo, TipoDocumento(tipo), arquivo.name, _llm())
            st.session_state.acoes.extend((arquivo.name, a) for a in res.acoes)
            st.success(f"{len(res.acoes)} ações extraídas")
            if projeto_id_selecionado is not None:
                with session_factory() as sess:
                    documento = salvar_documento_com_acoes(
                        sess, projeto_id_selecionado, arquivo.name,
                        TipoDocumento(tipo), res.resumo_documento, res.acoes,
                        conteudo_bruto=conteudo,
                    )
                reindexar_documento(_engine(), documento.id, projeto_id_selecionado, conteudo)
            else:
                st.warning("Selecione ou crie um projeto na barra lateral para salvar estas ações.")
            with st.expander("Resumo do documento"):
                st.write(res.resumo_documento)
        except DocumentoIlegivelError as e:
            st.error(f"Documento ilegível: {e}")
        except Exception as e:
            logger.exception("falha extração")
            st.error("Não foi possível concluir a operação. Verifique o arquivo e tente novamente.")
            with st.expander("Detalhes técnicos"):
                st.code(f"{type(e).__name__}: {e}")

    if st.session_state.acoes:
        f1, f2 = st.columns(2)
        filtro_status = f1.selectbox("Filtrar por status", ["Todos", "Pendentes", "Concluídas"])
        responsaveis = sorted({a.responsavel or "—" for _, a in st.session_state.acoes})
        filtro_resp = f2.selectbox("Filtrar por responsável", ["Todos", *responsaveis])

        linhas = list(st.session_state.acoes)
        if filtro_status == "Pendentes":
            linhas = [(n, a) for n, a in linhas if a.status != StatusAcao.CONCLUIDA]
        elif filtro_status == "Concluídas":
            linhas = [(n, a) for n, a in linhas if a.status == StatusAcao.CONCLUIDA]
        if filtro_resp != "Todos":
            linhas = [(n, a) for n, a in linhas if (a.responsavel or "—") == filtro_resp]

        # column_config não permite colorir células condicionalmente por valor
        # (só formata a coluna inteira). Alternativa mais próxima: prefixo de
        # emoji colorido no texto do status.
        cor_status = {
            StatusAcao.CONCLUIDA: "🟢",
            StatusAcao.ATRASADA: "🔴",
            StatusAcao.EM_ANDAMENTO: "🟡",
            StatusAcao.NAO_INICIADA: "⚪",
            StatusAcao.INDETERMINADO: "⚪",
        }
        st.dataframe(
            [
                {
                    "Documento": n, "Descrição": a.descricao, "Responsável": a.responsavel or "—",
                    "Prazo": a.prazo,
                    "Status": f"{cor_status.get(a.status, '⚪')} {a.status.value}",
                    "Confiança": a.confianca,
                }
                for n, a in linhas
            ],
            use_container_width=True,
            hide_index=True,
            column_config={
                "Prazo": st.column_config.DateColumn(format="DD/MM/YYYY"),
                "Confiança": st.column_config.ProgressColumn(
                    format="%.2f", min_value=0.0, max_value=1.0
                ),
            },
        )
    else:
        st.info("Nenhuma ação extraída ainda. Envie uma ata ou status report acima para começar.")

with aba_crono:
    crono_file = st.file_uploader("Cronograma MS Project (PDF)", type=["pdf"], key="crono")
    nome_proj = st.text_input("Nome do projeto", value="Projeto")
    if crono_file and st.button("Analisar cronograma", type="primary"):
        try:
            conteudo = ler_documento(_salvar_tmp(crono_file))
            cr = parsear_cronograma(
                conteudo, projeto_id=projeto_id_selecionado or 0, nome_projeto=nome_proj
            )
            st.session_state.cronograma = cr
            if projeto_id_selecionado is not None:
                with session_factory() as sess:
                    salvar_cronograma(sess, projeto_id_selecionado, cr.tarefas)
            else:
                st.warning(
                    "Selecione ou crie um projeto na barra lateral para salvar o cronograma."
                )
        except Exception as e:
            logger.exception("falha cronograma")
            st.error("Não foi possível concluir a operação. Verifique o arquivo e tente novamente.")
            with st.expander("Detalhes técnicos"):
                st.code(f"{type(e).__name__}: {e}")

    cr = st.session_state.cronograma
    if cr:
        saude = avaliar_saude(cr, [a.status for _, a in st.session_state.acoes])

        ESTILO_SAUDE = {
            NivelSaude.ATRASADO: (VERMELHO, BRANCO, "🔴"),
            NivelSaude.EM_RISCO: (AMARELO, CINZA_ESCURO, "⚠️"),
            NivelSaude.NO_PRAZO: (VERDE_CLARO, BRANCO, "✅"),
            NivelSaude.SEM_DADOS: (CINZA_CLARO, CINZA_ESCURO, "—"),
        }
        pct = saude.percentual_concluido or 0.0
        pct_barra = min(pct, PCT_COMPLETO)
        nivel_label = saude.nivel.value.replace("_", " ")
        cor_fundo_saude, cor_texto_saude, icone_saude = ESTILO_SAUDE[saude.nivel]

        col1, col2, col3 = st.columns(3)
        with col1:
            card_saude(
                titulo="Saúde",
                valor=nivel_label,
                subtitulo=None,
                cor_fundo=cor_fundo_saude,
                cor_texto=cor_texto_saude,
                icone=icone_saude,
            )
        with col2:
            st.markdown(
                f"""
                <div style="background:{BRANCO}; border:1px solid {CINZA_CLARO};
                            border-radius:8px; padding:1.2rem; text-align:center;">
                    <div style="font-size:0.85rem; text-transform:uppercase; color:{CINZA_MEDIO};">
                        % Concluído
                    </div>
                    <div style="font-weight:700; color:{CINZA_ESCURO}; margin-bottom:0.4rem;">
                        {pct:.0f}%
                    </div>
                    <div style="background:{CINZA_CLARO}; border-radius:6px;
                                height:0.8rem; overflow:hidden;">
                        <div style="background:{VERDE_CLARO}; width:{pct_barra:.0f}%;
                                    height:100%;"></div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with col3:
            cor_qtd = VERMELHO if saude.tarefas_atrasadas > 0 else VERDE_CLARO
            card_saude(
                titulo="Tarefas atrasadas",
                valor=f'<span style="color:{cor_qtd};">{saude.tarefas_atrasadas}</span>',
                subtitulo=None,
                cor_fundo=CINZA_ESCURO,
                cor_texto=BRANCO,
                icone="",
            )

        st.info(saude.justificativa)

        tarefas_reais = [t for t in cr.tarefas if not t.eh_resumo]
        contagem = {"Concluídas": 0, "No Prazo": 0, "Atrasadas": 0, "Futuras": 0}
        for t in tarefas_reais:
            if t.atrasada:
                contagem["Atrasadas"] += 1
            elif t.percentual_concluido >= PCT_COMPLETO:
                contagem["Concluídas"] += 1
            elif t.percentual_concluido > 0:
                contagem["No Prazo"] += 1
            else:
                contagem["Futuras"] += 1

        st.subheader("Tarefas por status")
        st.bar_chart(
            {k: [v] for k, v in contagem.items()},
            color=[VERDE_CLARO, AZUL, VERMELHO, CINZA_CLARO],
        )

        st.subheader("Tarefas atrasadas")
        atrasadas = [t for t in tarefas_reais if t.atrasada]
        if atrasadas:
            st.dataframe(
                [
                    {
                        "ID": t.id_tarefa, "Tarefa": t.nome,
                        "Concluído": f"{t.percentual_concluido:.0f}%",
                        "Esperado": (
                            f"{t.percentual_esperado:.0f}%" if t.percentual_esperado else "—"
                        ),
                        "Término": t.termino.isoformat() if t.termino else "—",
                        "Baseline": t.termino_baseline.isoformat() if t.termino_baseline else "—",
                    }
                    for t in atrasadas
                ],
                use_container_width=True, hide_index=True,
            )
        else:
            st.success("Nenhuma tarefa atrasada detectada.")

        st.divider()
        st.subheader("Status Report para o Cliente")
        if st.button("Gerar Status Report (PPTX)", type="primary"):
            with st.spinner("Gerando apresentação..."):
                with session_factory() as sess:
                    projeto_atual = next(
                        (p for p in listar_projetos(sess) if p.id == projeto_id_selecionado),
                        None,
                    )
                cliente = projeto_atual.cliente if projeto_atual else None
                pptx_bytes = gerar_status_report_pptx(cr, cliente, date.today())
            st.download_button(
                "Baixar apresentação",
                data=pptx_bytes,
                file_name=f"status_report_{_slug(cr.nome_projeto)}.pptx",
                mime=(
                    "application/vnd.openxmlformats-officedocument"
                    ".presentationml.presentation"
                ),
            )
    else:
        st.info(
            "Nenhum cronograma carregado. Envie um PDF de cronograma acima para "
            "visualizar a saúde do projeto."
        )

with aba_chat:
    st.session_state.setdefault("historico_chat", [])

    if st.button("Limpar conversa"):
        st.session_state.historico_chat = []
        st.rerun()

    for msg in st.session_state.historico_chat:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])
            if msg.get("fontes"):
                with st.expander("Fontes"):
                    for fonte in msg["fontes"]:
                        st.caption(fonte)

    pergunta = st.chat_input("Pergunte sobre o projeto...")
    if pergunta:
        if projeto_id_selecionado is None:
            st.warning("Selecione ou crie um projeto na barra lateral antes de perguntar.")
        else:
            st.session_state.historico_chat.append({"role": "user", "content": pergunta})
            with st.chat_message("user"):
                st.write(pergunta)

            trechos = buscar(_engine(), pergunta, k=5, projeto_id=projeto_id_selecionado)
            with st.chat_message("assistant"):
                if not trechos:
                    resposta_texto = "Sem documentos indexados para este projeto."
                    st.write(resposta_texto)
                    st.session_state.historico_chat.append(
                        {"role": "assistant", "content": resposta_texto, "fontes": []}
                    )
                else:
                    partes_contexto = [f"Projeto: {projeto_nome_selecionado}"]
                    if st.session_state.cronograma:
                        saude_atual = avaliar_saude(
                            st.session_state.cronograma,
                            [a.status for _, a in st.session_state.acoes],
                        )
                        partes_contexto.append(saude_atual.justificativa)
                    contexto_projeto = " | ".join(partes_contexto)

                    with st.spinner("Consultando documentos..."):
                        resposta = responder_pergunta(pergunta, trechos, contexto_projeto, _llm())
                    st.write(resposta.resposta)
                    if resposta.fontes:
                        with st.expander("Fontes"):
                            for fonte in resposta.fontes:
                                st.caption(fonte)
                    st.session_state.historico_chat.append(
                        {
                            "role": "assistant",
                            "content": resposta.resposta,
                            "fontes": resposta.fontes,
                        }
                    )
