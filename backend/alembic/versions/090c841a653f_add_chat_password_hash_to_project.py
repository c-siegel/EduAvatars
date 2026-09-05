"""add chat_password_hash to project

Revision ID: 090c841a653f
Revises: 5fb480350bec
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '090c841a653f'
down_revision: Union[str, None] = '5fb480350bec'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('chat_password_hash', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('project', 'chat_password_hash')
