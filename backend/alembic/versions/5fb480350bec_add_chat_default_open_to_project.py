"""add chat_default_open to project

Revision ID: 5fb480350bec
Revises: fd1c28a1d461
Create Date: 2026-08-18 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '5fb480350bec'
down_revision: Union[str, None] = 'fd1c28a1d461'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('chat_default_open', sa.Boolean(), nullable=False, server_default=sa.true()))


def downgrade() -> None:
    op.drop_column('project', 'chat_default_open')
