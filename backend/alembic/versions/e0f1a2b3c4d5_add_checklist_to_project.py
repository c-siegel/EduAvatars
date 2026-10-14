"""add checklist to project

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-10-14 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, None] = 'd9e0f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('checklist_enabled', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('checklist_visible', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('checklist_ordered', sa.Boolean(), nullable=False, server_default=sa.true()))
        batch_op.add_column(sa.Column('checklist_json', sa.String(), nullable=False, server_default='[]'))


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('checklist_json')
        batch_op.drop_column('checklist_ordered')
        batch_op.drop_column('checklist_visible')
        batch_op.drop_column('checklist_enabled')
