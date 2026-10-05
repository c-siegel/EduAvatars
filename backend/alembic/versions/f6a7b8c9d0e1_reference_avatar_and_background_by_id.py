"""reference avatar and background by id instead of url

Projects used to store the URL of their avatar model and background image (e.g.
"/avatar-models/{id}/file"), which tied stored data to the API's route layout. They now store the
library item's id (or, for a bundled default avatar, its name) and the API builds the URL.

Revision ID: f6a7b8c9d0e1
Revises: f4a5b6c7d8e9
Create Date: 2026-10-05 15:00:00.000000

"""
import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'f4a5b6c7d8e9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# The URL shapes stored before this revision (router-relative, no API prefix).
_LIBRARY_AVATAR_RE = re.compile(r"^/avatar-models/([^/]+)/file$")
_BUILTIN_AVATAR_RE = re.compile(r"^/avatars/([a-z0-9-]{1,40})\.glb$")
_BACKGROUND_RE = re.compile(r"^/backgrounds/([^/]+)/file$")


def upgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('avatar_model_id', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('builtin_avatar', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('avatar_background_id', sa.String(), nullable=True))
        batch_op.create_index(batch_op.f('ix_project_avatar_model_id'), ['avatar_model_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_project_avatar_background_id'), ['avatar_background_id'], unique=False)
        batch_op.create_foreign_key('fk_project_avatar_model_id_avatarmodel', 'avatarmodel', ['avatar_model_id'], ['id'])
        batch_op.create_foreign_key(
            'fk_project_avatar_background_id_backgroundimage', 'backgroundimage', ['avatar_background_id'], ['id']
        )

    # Carry every existing reference over. A URL that matches none of the known shapes (it never
    # rendered anything but the default look anyway) is dropped.
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT id, avatar_model_url, avatar_background_url FROM project")).fetchall()
    for project_id, avatar_url, background_url in rows:
        values = {"avatar_model_id": None, "builtin_avatar": None, "avatar_background_id": None}
        if match := _LIBRARY_AVATAR_RE.match(avatar_url or ""):
            values["avatar_model_id"] = match.group(1)
        elif match := _BUILTIN_AVATAR_RE.match(avatar_url or ""):
            values["builtin_avatar"] = match.group(1)
        if match := _BACKGROUND_RE.match(background_url or ""):
            values["avatar_background_id"] = match.group(1)
        if any(values.values()):
            connection.execute(
                sa.text(
                    "UPDATE project SET avatar_model_id = :avatar_model_id, builtin_avatar = :builtin_avatar, "
                    "avatar_background_id = :avatar_background_id WHERE id = :id"
                ),
                {**values, "id": project_id},
            )

    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_column('avatar_model_url')
        batch_op.drop_column('avatar_background_url')


def downgrade() -> None:
    with op.batch_alter_table('project') as batch_op:
        batch_op.add_column(sa.Column('avatar_model_url', sa.String(), nullable=True))
        batch_op.add_column(sa.Column('avatar_background_url', sa.String(), nullable=True))

    connection = op.get_bind()
    rows = connection.execute(
        sa.text("SELECT id, avatar_model_id, builtin_avatar, avatar_background_id FROM project")
    ).fetchall()
    for project_id, avatar_id, builtin, background_id in rows:
        avatar_url = f"/avatar-models/{avatar_id}/file" if avatar_id else (f"/avatars/{builtin}.glb" if builtin else None)
        background_url = f"/backgrounds/{background_id}/file" if background_id else None
        if avatar_url or background_url:
            connection.execute(
                sa.text("UPDATE project SET avatar_model_url = :a, avatar_background_url = :b WHERE id = :id"),
                {"a": avatar_url, "b": background_url, "id": project_id},
            )

    with op.batch_alter_table('project') as batch_op:
        batch_op.drop_constraint('fk_project_avatar_background_id_backgroundimage', type_='foreignkey')
        batch_op.drop_constraint('fk_project_avatar_model_id_avatarmodel', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_project_avatar_background_id'))
        batch_op.drop_index(batch_op.f('ix_project_avatar_model_id'))
        batch_op.drop_column('avatar_background_id')
        batch_op.drop_column('builtin_avatar')
        batch_op.drop_column('avatar_model_id')
