"""add knowledge bibliography entries

A knowledge base's imported BibTeX entries (features/knowledge/bibtex.py): the bibliographic
layer of the metadata of documents linked to them by key. Unique per knowledge base and key.

Revision ID: 7bf9a2464247
Revises: 447eaf782955
Create Date: 2026-10-09 13:47:30.182695

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '7bf9a2464247'
down_revision: Union[str, None] = '447eaf782955'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('knowledgebibentry',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('knowledge_base_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('key', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('fields_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledgebase.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('knowledge_base_id', 'key')
    )
    op.create_index(op.f('ix_knowledgebibentry_knowledge_base_id'), 'knowledgebibentry', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_knowledgebibentry_user_id'), 'knowledgebibentry', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_knowledgebibentry_user_id'), table_name='knowledgebibentry')
    op.drop_index(op.f('ix_knowledgebibentry_knowledge_base_id'), table_name='knowledgebibentry')
    op.drop_table('knowledgebibentry')
