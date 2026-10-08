"""add knowledge bases (RAG), their project settings and admin limits

Teachers' knowledge bases and documents (features/knowledge/), a retry queue for deletes the
knowledge service couldn't be told about yet, the project's knowledge settings, and the
admin-editable upload limits on the site settings row. Every new NOT NULL column has a
server_default, so existing rows get the documented defaults.

Revision ID: e1f2a3b4c5d6
Revises: d0e1f2a3b4c5
Create Date: 2026-10-08 12:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_SITE_SETTINGS_LIMITS = (
    ('rag_max_upload_mb', '20'),
    ('rag_max_pages', '500'),
    ('rag_max_chars_per_document', '2000000'),
    ('rag_max_documents_per_kb', '50'),
    ('rag_max_kb_per_user', '20'),
    ('rag_user_quota_mb', '200'),
    ('rag_upload_rate_per_10min', '30'),
)


def upgrade() -> None:
    op.create_table(
        'knowledgebase',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('description', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('embedding_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('embedding_api_key_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('embedding_model', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['embedding_api_key_id'], ['userapikey.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_knowledgebase_user_id'), 'knowledgebase', ['user_id'], unique=False)
    op.create_index(
        op.f('ix_knowledgebase_embedding_api_key_id'), 'knowledgebase', ['embedding_api_key_id'], unique=False
    )

    op.create_table(
        'knowledgedocument',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('knowledge_base_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('filename', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('file_type', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('parser', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=True),
        sa.Column('chunk_count', sa.Integer(), nullable=True),
        sa.Column('truncated', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledgebase.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_knowledgedocument_knowledge_base_id'), 'knowledgedocument', ['knowledge_base_id'], unique=False
    )
    op.create_index(op.f('ix_knowledgedocument_user_id'), 'knowledgedocument', ['user_id'], unique=False)
    op.create_index(op.f('ix_knowledgedocument_sha256'), 'knowledgedocument', ['sha256'], unique=False)

    op.create_table(
        'ragpendingdeletion',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('target_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(
            sa.Column('knowledge_mode', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='off')
        )
        batch_op.add_column(sa.Column('knowledge_top_k', sa.Integer(), nullable=False, server_default='4'))
        batch_op.add_column(
            sa.Column(
                'knowledge_base_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='[]'
            )
        )

    with op.batch_alter_table('sitesettings') as batch_op:
        for column, default in _SITE_SETTINGS_LIMITS:
            batch_op.add_column(sa.Column(column, sa.Integer(), nullable=False, server_default=default))


def downgrade() -> None:
    with op.batch_alter_table('sitesettings') as batch_op:
        for column, _ in reversed(_SITE_SETTINGS_LIMITS):
            batch_op.drop_column(column)
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('knowledge_base_ids_json')
        batch_op.drop_column('knowledge_top_k')
        batch_op.drop_column('knowledge_mode')
    op.drop_table('ragpendingdeletion')
    op.drop_index(op.f('ix_knowledgedocument_sha256'), table_name='knowledgedocument')
    op.drop_index(op.f('ix_knowledgedocument_user_id'), table_name='knowledgedocument')
    op.drop_index(op.f('ix_knowledgedocument_knowledge_base_id'), table_name='knowledgedocument')
    op.drop_table('knowledgedocument')
    op.drop_index(op.f('ix_knowledgebase_embedding_api_key_id'), table_name='knowledgebase')
    op.drop_index(op.f('ix_knowledgebase_user_id'), table_name='knowledgebase')
    op.drop_table('knowledgebase')
