"""add stt_server_engine to project

Revision ID: c9d0e1f2a3b4
Revises: 06ba481a805c
Create Date: 2026-10-06 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = '06ba481a805c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable: NULL keeps every existing project on the deployment's STT_ENGINE, as before.
    op.add_column('project', sa.Column('stt_server_engine', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('project', 'stt_server_engine')
