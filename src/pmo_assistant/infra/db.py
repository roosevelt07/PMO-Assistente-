"""Persistência via SQLAlchemy 2.0 tipado. WAL habilitado para concorrência.

Tabelas espelham os schemas Pydantic de core/models.py. Conversão acontece
nas funções de repositório (a adicionar conforme necessidade).
Em produção, schema via Alembic; inicializar_schema só para dev.
"""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import (
    Date,
    DateTime,
    Engine,
    Float,
    ForeignKey,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    Session,
    mapped_column,
    relationship,
    sessionmaker,
)

DEFAULT_DB_PATH = Path("data/pmo.db")


class Base(DeclarativeBase):
    pass


class ProjetoORM(Base):
    __tablename__ = "projetos"
    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(200))
    cliente: Mapped[str | None] = mapped_column(String(200), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    documentos: Mapped[list[DocumentoORM]] = relationship(back_populates="projeto")
    tarefas: Mapped[list[TarefaORM]] = relationship(back_populates="projeto")


class DocumentoORM(Base):
    __tablename__ = "documentos"
    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"))
    nome_arquivo: Mapped[str] = mapped_column(String(300))
    tipo: Mapped[str] = mapped_column(String(40))
    enviado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    resumo: Mapped[str | None] = mapped_column(String(1500), nullable=True)
    conteudo_bruto: Mapped[str | None] = mapped_column(Text, nullable=True)
    projeto: Mapped[ProjetoORM] = relationship()
    acoes: Mapped[list[AcaoORM]] = relationship(back_populates="documento")


class AcaoORM(Base):
    __tablename__ = "acoes"
    id: Mapped[int] = mapped_column(primary_key=True)
    documento_id: Mapped[int] = mapped_column(ForeignKey("documentos.id"))
    descricao: Mapped[str] = mapped_column(String(500))
    responsavel: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prazo: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(40))
    contexto_origem: Mapped[str] = mapped_column(String(300))
    confianca: Mapped[float] = mapped_column(Float)
    criado_em: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    documento: Mapped[DocumentoORM] = relationship(back_populates="acoes")


class TarefaORM(Base):
    __tablename__ = "tarefas"
    id: Mapped[int] = mapped_column(primary_key=True)
    projeto_id: Mapped[int] = mapped_column(ForeignKey("projetos.id"))
    id_tarefa: Mapped[int] = mapped_column()
    nome: Mapped[str] = mapped_column(String(400))
    percentual_concluido: Mapped[float] = mapped_column(Float)
    percentual_esperado: Mapped[float | None] = mapped_column(Float, nullable=True)
    termino_baseline: Mapped[date | None] = mapped_column(Date, nullable=True)
    termino: Mapped[date | None] = mapped_column(Date, nullable=True)
    atrasada: Mapped[bool] = mapped_column(default=False)
    projeto: Mapped[ProjetoORM] = relationship(back_populates="tarefas")


def criar_engine(caminho: Path | None = None) -> Engine:
    db_path = caminho or DEFAULT_DB_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", echo=False)

    @event.listens_for(engine, "connect")
    def _wal(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def criar_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def inicializar_schema(engine: Engine) -> None:
    logger.warning("criando schema via metadata — em produção use Alembic")
    Base.metadata.create_all(engine)
