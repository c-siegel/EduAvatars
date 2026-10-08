"""replace chat_default_open with chat_layout

Revision ID: d0e1f2a3b4c5
Revises: c9d0e1f2a3b4
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd0e1f2a3b4c5'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'project', sa.Column('chat_layout', sa.String(), nullable=False, server_default='avatar_chat')
    )
    # A collapsed chat keeps starting collapsed.
    op.execute(
        sa.text("UPDATE project SET chat_layout = 'avatar_chat_collapsed' WHERE chat_default_open = :off").bindparams(
            off=False
        )
    )
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('chat_default_open')


def downgrade() -> None:
    op.add_column('project', sa.Column('chat_default_open', sa.Boolean(), nullable=False, server_default=sa.true()))
    op.execute(
        sa.text("UPDATE project SET chat_default_open = :off WHERE chat_layout = 'avatar_chat_collapsed'").bindparams(
            off=False
        )
    )
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('chat_layout')
