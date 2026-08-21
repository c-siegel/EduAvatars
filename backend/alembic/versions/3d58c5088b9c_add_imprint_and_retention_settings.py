"""add imprint and retention settings

Revision ID: 3d58c5088b9c
Revises: a4cf17056172
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3d58c5088b9c'
down_revision: Union[str, None] = 'a4cf17056172'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('sitesettings', sa.Column('contact_phone', sa.String(), nullable=True))
    op.add_column('sitesettings', sa.Column('provider_name', sa.String(), nullable=True))
    op.add_column('sitesettings', sa.Column('provider_street', sa.String(), nullable=True))
    op.add_column('sitesettings', sa.Column('provider_city', sa.String(), nullable=True))
    op.add_column('sitesettings', sa.Column('provider_country', sa.String(), nullable=True))
    # 0 = keep forever, matching the behaviour before this column existed — an upgrade must never
    # start deleting existing conversations on its own.
    op.add_column(
        'sitesettings',
        sa.Column('conversation_retention_days', sa.Integer(), nullable=False, server_default='0'),
    )


def downgrade() -> None:
    op.drop_column('sitesettings', 'conversation_retention_days')
    op.drop_column('sitesettings', 'provider_country')
    op.drop_column('sitesettings', 'provider_city')
    op.drop_column('sitesettings', 'provider_street')
    op.drop_column('sitesettings', 'provider_name')
    op.drop_column('sitesettings', 'contact_phone')
