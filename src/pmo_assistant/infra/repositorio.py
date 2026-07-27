"""Funções de persistência: Session -> ORM -> commit.

Converte schemas Pydantic de core/models.py para os modelos ORM de infra/db.py.
Não expõe SQL bruto para chamadores — cada função recebe/devolve tipos ORM ou
tipos primitivos, nunca Session cru de fora do escopo da chamada.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pmo_assistant.infra.db import AcaoORM, DocumentoORM, ProjetoORM, TarefaORM

if TYPE_CHECKING:
    from pmo_assistant.core.models import AcaoExtraida, TarefaCronograma, TipoDocumento


def salvar_projeto(session: Session, nome: str, cliente: str | None = None) -> ProjetoORM:
    projeto = ProjetoORM(nome=nome, cliente=cliente)
    session.add(projeto)
    session.commit()
    session.refresh(projeto)
    return projeto


def salvar_documento_com_acoes(
    session: Session,
    projeto_id: int,
    nome_arquivo: str,
    tipo: TipoDocumento,
    resumo: str | None,
    acoes: list[AcaoExtraida],
    conteudo_bruto: str | None = None,
) -> DocumentoORM:
    documento = DocumentoORM(
        projeto_id=projeto_id,
        nome_arquivo=nome_arquivo,
        tipo=tipo.value,
        resumo=resumo,
        conteudo_bruto=conteudo_bruto,
    )
    documento.acoes = [
        AcaoORM(
            descricao=acao.descricao,
            responsavel=acao.responsavel,
            prazo=acao.prazo,
            status=acao.status.value,
            contexto_origem=acao.contexto_origem,
            confianca=acao.confianca,
        )
        for acao in acoes
    ]
    session.add(documento)
    session.commit()
    session.refresh(documento)
    return documento


def salvar_cronograma(
    session: Session, projeto_id: int, tarefas: list[TarefaCronograma]
) -> list[TarefaORM]:
    # Linhas-resumo (eh_resumo=True) são agregados de fase, não tarefas reais, e
    # TarefaORM não tem essa coluna (ver Armadilhas Conhecidas no CLAUDE.md) —
    # persistimos apenas as tarefas de folha.
    tarefas_orm = [
        TarefaORM(
            projeto_id=projeto_id,
            id_tarefa=t.id_tarefa,
            nome=t.nome,
            percentual_concluido=t.percentual_concluido,
            percentual_esperado=t.percentual_esperado,
            termino_baseline=t.termino_baseline,
            termino=t.termino,
            atrasada=t.atrasada,
        )
        for t in tarefas
        if not t.eh_resumo
    ]
    session.add_all(tarefas_orm)
    session.commit()
    for tarefa_orm in tarefas_orm:
        session.refresh(tarefa_orm)
    return tarefas_orm


def listar_projetos(session: Session) -> list[ProjetoORM]:
    return list(session.execute(select(ProjetoORM)).scalars().all())


def listar_acoes_por_projeto(session: Session, projeto_id: int) -> list[AcaoORM]:
    stmt = (
        select(AcaoORM)
        .join(DocumentoORM, AcaoORM.documento_id == DocumentoORM.id)
        .where(DocumentoORM.projeto_id == projeto_id)
        .options(selectinload(AcaoORM.documento))
    )
    return list(session.execute(stmt).scalars().all())


def listar_tarefas_por_projeto(session: Session, projeto_id: int) -> list[TarefaORM]:
    stmt = select(TarefaORM).where(TarefaORM.projeto_id == projeto_id)
    return list(session.execute(stmt).scalars().all())
