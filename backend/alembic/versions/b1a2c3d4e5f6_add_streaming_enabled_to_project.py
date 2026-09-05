"""add streaming_enabled to project

Revision ID: b1a2c3d4e5f6
Revises: 3d58c5088b9c
Create Date: 2026-08-25 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b1a2c3d4e5f6'
down_revision: Union[str, None] = '3d58c5088b9c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('streaming_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('project', 'streaming_enabled')
