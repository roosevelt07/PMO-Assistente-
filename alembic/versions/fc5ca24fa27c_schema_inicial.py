"""schema_inicial

Revision ID: fc5ca24fa27c
Revises: 
Create Date: 2026-07-17 15:18:21.588244

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'fc5ca24fa27c'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Corrigido: o stub original gerado pelo `alembic revision` (sem --autogenerate)
    # ficava vazio porque o banco de dev já tinha o schema criado via
    # inicializar_schema()/metadata. Isso quebrava `alembic upgrade head` contra um
    # banco realmente vazio (Streamlit Cloud). DDL abaixo replicada de
    # infra/db.py::Base.metadata via autogenerate contra banco vazio.
    op.create_table(
        'projetos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=200), nullable=False),
        sa.Column('cliente', sa.String(length=200), nullable=True),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'documentos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('projeto_id', sa.Integer(), nullable=False),
        sa.Column('nome_arquivo', sa.String(length=300), nullable=False),
        sa.Column('tipo', sa.String(length=40), nullable=False),
        sa.Column('enviado_em', sa.DateTime(), nullable=False),
        sa.Column('resumo', sa.String(length=1500), nullable=True),
        sa.ForeignKeyConstraint(['projeto_id'], ['projetos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'tarefas',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('projeto_id', sa.Integer(), nullable=False),
        sa.Column('id_tarefa', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=400), nullable=False),
        sa.Column('percentual_concluido', sa.Float(), nullable=False),
        sa.Column('percentual_esperado', sa.Float(), nullable=True),
        sa.Column('termino_baseline', sa.Date(), nullable=True),
        sa.Column('termino', sa.Date(), nullable=True),
        sa.Column('atrasada', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['projeto_id'], ['projetos.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'acoes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('documento_id', sa.Integer(), nullable=False),
        sa.Column('descricao', sa.String(length=500), nullable=False),
        sa.Column('responsavel', sa.String(length=120), nullable=True),
        sa.Column('prazo', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=40), nullable=False),
        sa.Column('contexto_origem', sa.String(length=300), nullable=False),
        sa.Column('confianca', sa.Float(), nullable=False),
        sa.Column('criado_em', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['documento_id'], ['documentos.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('acoes')
    op.drop_table('tarefas')
    op.drop_table('documentos')
    op.drop_table('projetos')
