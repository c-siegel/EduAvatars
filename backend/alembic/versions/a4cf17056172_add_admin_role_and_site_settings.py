"""add admin role and site settings

Revision ID: a4cf17056172
Revises: 090c841a653f
Create Date: 2026-08-21 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a4cf17056172'
down_revision: Union[str, None] = '090c841a653f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('is_admin', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('user', sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        'sitesettings',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_email', sa.String(), nullable=True),
        sa.Column('registration_enabled', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('sitesettings')
    op.drop_column('user', 'must_change_password')
    op.drop_column('user', 'is_admin')
