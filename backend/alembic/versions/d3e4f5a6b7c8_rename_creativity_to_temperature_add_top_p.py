"""rename creativity to temperature and add top_p to project

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-08-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd3e4f5a6b7c8'
down_revision: Union[str, None] = 'c2d3e4f5a6b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # The old "creativity" column was already sent to the model as `temperature` and nothing else
    # (see services/llm_service.py) — renaming keeps every existing project's setting instead of
    # resetting it to the default, which adding a fresh column would have done.
    op.alter_column('project', 'creativity', new_column_name='temperature')
    # 1.0 = "consider every token", i.e. the provider default, so existing projects behave exactly
    # as they did before this column existed.
    op.add_column('project', sa.Column('top_p', sa.Float(), nullable=False, server_default='1.0'))


def downgrade() -> None:
    op.drop_column('project', 'top_p')
    op.alter_column('project', 'temperature', new_column_name='creativity')
