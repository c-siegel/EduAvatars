"""add the pronunciation word list

Each teacher keeps their own list of terms the TTS should pronounce differently, per spoken
language (features/pronunciation). A new table only, so nothing existing needs batch mode; the
booleans get a server_default anyway so rows inserted outside the ORM stay valid.

Revision ID: 71642eb1b2db
Revises: d0e1f2a3b4c5
Create Date: 2026-10-09 12:53:19.655627

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '71642eb1b2db'
down_revision: Union[str, None] = 'd0e1f2a3b4c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'pronunciationentry',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('language', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('term', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('spoken', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('whole_word', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('case_sensitive', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('source_pack', sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'language', 'term', name='uq_pronunciationentry_user_language_term'),
    )
    op.create_index(op.f('ix_pronunciationentry_user_id'), 'pronunciationentry', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_pronunciationentry_user_id'), table_name='pronunciationentry')
    op.drop_table('pronunciationentry')
