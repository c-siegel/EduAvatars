"""add the voice clip library and project.tts_voice_clip_id

Teachers keep their own voice clips for local voice cloning (features/media/voices_router.py),
and a project can pick one (Project.tts_voice_clip_id). The project column gets its foreign key
in batch mode, since SQLite can't add a constraint to an existing table (it rebuilds the table).

Revision ID: 06ba481a805c
Revises: b8c9d0e1f2a3
Create Date: 2026-10-06 00:43:38.246530

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '06ba481a805c'
down_revision: Union[str, None] = 'b8c9d0e1f2a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'voiceclip',
        sa.Column('id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('user_id', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('name', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('file_path', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('sha256', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('duration_seconds', sa.Float(), nullable=False),
        sa.Column('consent_confirmed_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_voiceclip_user_id'), 'voiceclip', ['user_id'], unique=False)
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('tts_voice_clip_id', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.create_index(batch_op.f('ix_project_tts_voice_clip_id'), ['tts_voice_clip_id'], unique=False)
        batch_op.create_foreign_key('fk_project_tts_voice_clip_id_voiceclip', 'voiceclip', ['tts_voice_clip_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_constraint('fk_project_tts_voice_clip_id_voiceclip', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_project_tts_voice_clip_id'))
        batch_op.drop_column('tts_voice_clip_id')
    op.drop_index(op.f('ix_voiceclip_user_id'), table_name='voiceclip')
    op.drop_table('voiceclip')
