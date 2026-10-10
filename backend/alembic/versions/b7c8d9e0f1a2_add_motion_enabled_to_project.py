"""add motion_enabled to project

Revision ID: b7c8d9e0f1a2
Revises: 7bf9a2464247
Create Date: 2026-10-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = '7bf9a2464247'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # server_default true: existing projects get the avatar's body language too, the same default
    # new projects get from the model.
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('motion_enabled', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('motion_enabled')
