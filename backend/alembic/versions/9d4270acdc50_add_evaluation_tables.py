"""add evaluation tables (Ragas test sets and runs) and the per-run question cap

Teachers' test sets and test questions per knowledge base, and evaluation runs with one item per
question (features/evaluation/). The admin-editable cap on questions per run goes on the site
settings row with a server_default, so the existing row gets the documented default of 50.

Revision ID: 9d4270acdc50
Revises: f2a3b4c5d6e7
Create Date: 2026-10-08 17:53:46.304996

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9d4270acdc50'
down_revision: Union[str, None] = 'f2a3b4c5d6e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('evaltestset',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('knowledge_base_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['knowledge_base_id'], ['knowledgebase.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaltestset_knowledge_base_id'), 'evaltestset', ['knowledge_base_id'], unique=False)
    op.create_index(op.f('ix_evaltestset_user_id'), 'evaltestset', ['user_id'], unique=False)
    op.create_table('evalrun',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('project_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('test_set_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('judge_api_key_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('config_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('metrics_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('knowledge_base_ids_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('status', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('case_count', sa.Integer(), nullable=False),
    sa.Column('answered_count', sa.Integer(), nullable=False),
    sa.Column('scored_count', sa.Integer(), nullable=False),
    sa.Column('summary_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('finished_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['judge_api_key_id'], ['userapikey.id'], ),
    sa.ForeignKeyConstraint(['project_id'], ['project.id'], ),
    sa.ForeignKeyConstraint(['test_set_id'], ['evaltestset.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evalrun_judge_api_key_id'), 'evalrun', ['judge_api_key_id'], unique=False)
    op.create_index(op.f('ix_evalrun_project_id'), 'evalrun', ['project_id'], unique=False)
    op.create_index(op.f('ix_evalrun_test_set_id'), 'evalrun', ['test_set_id'], unique=False)
    op.create_index(op.f('ix_evalrun_user_id'), 'evalrun', ['user_id'], unique=False)
    op.create_table('evaltestcase',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('test_set_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('question', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('origin', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('approved', sa.Boolean(), nullable=False),
    sa.Column('source_chunk_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['test_set_id'], ['evaltestset.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['user.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evaltestcase_test_set_id'), 'evaltestcase', ['test_set_id'], unique=False)
    op.create_index(op.f('ix_evaltestcase_user_id'), 'evaltestcase', ['user_id'], unique=False)
    op.create_table('evalrunitem',
    sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('run_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('test_case_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('position', sa.Integer(), nullable=False),
    sa.Column('question', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('reference', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('answer', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('contexts_json', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
    sa.Column('scores_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.Column('retrieval_ms', sa.Float(), nullable=True),
    sa.Column('llm_ms', sa.Float(), nullable=True),
    sa.Column('error_code', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
    sa.ForeignKeyConstraint(['run_id'], ['evalrun.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_evalrunitem_run_id'), 'evalrunitem', ['run_id'], unique=False)
    with op.batch_alter_table('sitesettings') as batch_op:
        batch_op.add_column(
            sa.Column('rag_eval_max_cases_per_run', sa.Integer(), nullable=False, server_default='50')
        )


def downgrade() -> None:
    with op.batch_alter_table('sitesettings') as batch_op:
        batch_op.drop_column('rag_eval_max_cases_per_run')
    op.drop_index(op.f('ix_evalrunitem_run_id'), table_name='evalrunitem')
    op.drop_table('evalrunitem')
    op.drop_index(op.f('ix_evaltestcase_user_id'), table_name='evaltestcase')
    op.drop_index(op.f('ix_evaltestcase_test_set_id'), table_name='evaltestcase')
    op.drop_table('evaltestcase')
    op.drop_index(op.f('ix_evalrun_user_id'), table_name='evalrun')
    op.drop_index(op.f('ix_evalrun_test_set_id'), table_name='evalrun')
    op.drop_index(op.f('ix_evalrun_project_id'), table_name='evalrun')
    op.drop_index(op.f('ix_evalrun_judge_api_key_id'), table_name='evalrun')
    op.drop_table('evalrun')
    op.drop_index(op.f('ix_evaltestset_user_id'), table_name='evaltestset')
    op.drop_index(op.f('ix_evaltestset_knowledge_base_id'), table_name='evaltestset')
    op.drop_table('evaltestset')
