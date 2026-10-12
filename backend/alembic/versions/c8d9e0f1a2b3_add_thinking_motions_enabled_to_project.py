"""add thinking_motions_enabled to project

Revision ID: c8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-10-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default false: existing projects keep behaving as before until a teacher opts in.
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('thinking_motions_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('thinking_motions_enabled')
