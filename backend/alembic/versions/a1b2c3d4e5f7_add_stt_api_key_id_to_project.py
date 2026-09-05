"""add stt_api_key_id to project

Revision ID: a1b2c3d4e5f7
Revises: e8ed0b25d641
Create Date: 2026-09-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'e8ed0b25d641'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('project', sa.Column('stt_api_key_id', sa.String(), nullable=True))
    op.create_index(op.f('ix_project_stt_api_key_id'), 'project', ['stt_api_key_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_project_stt_api_key_id'), table_name='project')
    op.drop_column('project', 'stt_api_key_id')
