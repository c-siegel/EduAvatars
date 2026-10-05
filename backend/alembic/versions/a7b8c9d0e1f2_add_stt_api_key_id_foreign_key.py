"""add the stt_api_key_id foreign key to project

a1b2c3d4e5f7 added project.stt_api_key_id but not the foreign key to userapikey that the model
declares (unlike llm_api_key_id/tts_api_key_id), so `alembic check` kept reporting it as missing.
SQLite can't add a constraint to an existing table, hence batch mode (it rebuilds the table).

Revision ID: a7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-10-05 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, None] = 'f6a7b8c9d0e1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.create_foreign_key('fk_project_stt_api_key_id_userapikey', 'userapikey', ['stt_api_key_id'], ['id'])


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_constraint('fk_project_stt_api_key_id_userapikey', type_='foreignkey')
