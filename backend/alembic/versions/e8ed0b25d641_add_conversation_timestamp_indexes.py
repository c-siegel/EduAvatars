"""add indexes on conversation.started_at and conversation.updated_at

Conversation is the fastest-growing table (every saved chat), and both columns are already
queried without an index: analytics_service.py filters/orders on updated_at/started_at, and
retention_service.py deletes WHERE updated_at < cutoff — all full-table scans without this.

Revision ID: e8ed0b25d641
Revises: e5f6a7b8c9d0
Create Date: 2026-09-05 11:01:17.562831

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'e8ed0b25d641'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(op.f('ix_conversation_started_at'), 'conversation', ['started_at'], unique=False)
    op.create_index(op.f('ix_conversation_updated_at'), 'conversation', ['updated_at'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_conversation_updated_at'), table_name='conversation')
    op.drop_index(op.f('ix_conversation_started_at'), table_name='conversation')
