"""add the question kind to evaluation test cases and run items

Test questions now come in three kinds (grounded: drafted from a passage, topic: asked about the
subject without knowing the material, offtopic: outside the subject), which decide what they
measure. Existing drafted questions were all drafted from passages; the ones the teacher wrote or
imported are the kind of question a student asks about the subject. Run items copy the kind, so
the summary can be split by it. New NOT NULL columns have a server_default.

Revision ID: c3d4e5f6a7b9
Revises: 9d4270acdc50
Create Date: 2026-10-09 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b9'
down_revision: Union[str, None] = '9d4270acdc50'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('evaltestcase') as batch_op:
        batch_op.add_column(
            sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='grounded')
        )
    with op.batch_alter_table('evalrunitem') as batch_op:
        batch_op.add_column(
            sa.Column('kind', sqlmodel.sql.sqltypes.AutoString(), nullable=False, server_default='grounded')
        )
    op.execute("UPDATE evaltestcase SET kind = 'topic' WHERE origin != 'generated'")


def downgrade() -> None:
    with op.batch_alter_table('evalrunitem') as batch_op:
        batch_op.drop_column('kind')
    with op.batch_alter_table('evaltestcase') as batch_op:
        batch_op.drop_column('kind')
