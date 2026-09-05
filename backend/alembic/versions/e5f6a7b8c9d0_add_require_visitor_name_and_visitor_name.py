"""add require_visitor_name to project and visitor_name to conversation

Revision ID: e5f6a7b8c9d0
Revises: d3e4f5a6b7c8
Create Date: 2026-08-31 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd3e4f5a6b7c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('require_visitor_name', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('conversation', sa.Column('visitor_name', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('conversation', 'visitor_name')
    op.drop_column('project', 'require_visitor_name')
