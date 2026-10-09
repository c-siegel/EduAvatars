"""add knowledgedocument.retryable

Whether the knowledge service still keeps a failed document's original, so the dashboard can offer
a one-click retry (POST /knowledge-documents/{id}/retry) instead of a re-upload.

Revision ID: f2a3b4c5d6e7
Revises: e1f2a3b4c5d6
Create Date: 2026-10-08 18:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f2a3b4c5d6e7'
down_revision: Union[str, None] = 'e1f2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('knowledgedocument') as batch_op:
        batch_op.add_column(sa.Column('retryable', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    with op.batch_alter_table('knowledgedocument') as batch_op:
        batch_op.drop_column('retryable')
