"""turn on-device transcription on by default, including for existing projects

On-device (WebGPU) transcription with Parakeet Redux replaced the old opt-in browser Whisper and
is now the default way voice input is transcribed, so every existing project is switched over
too. A project can still opt out in the Configurator afterwards.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-10-05 21:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b8c9d0e1f2a3'
down_revision: Union[str, None] = 'a7b8c9d0e1f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.alter_column('stt_browser_enabled', existing_type=sa.Boolean(), server_default=sa.true())
    op.execute(sa.text("UPDATE project SET stt_browser_enabled = :on").bindparams(on=True))


def downgrade() -> None:
    # Only the column default goes back — which projects had opted in before can't be recovered.
    with op.batch_alter_table('project') as batch_op:
        batch_op.alter_column('stt_browser_enabled', existing_type=sa.Boolean(), server_default=sa.false())
