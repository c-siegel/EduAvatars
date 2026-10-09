"""add source metadata to knowledge documents

The layers of a document's source metadata (features/knowledge/metadata.py): what the file's own
header said, what the teacher entered, and the BibTeX key of the linked bibliography entry. All
nullable — documents without metadata behave as before.

Revision ID: 447eaf782955
Revises: 71642eb1b2db
Create Date: 2026-10-09 13:45:44.119042

"""
from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '447eaf782955'
down_revision: Union[str, None] = '71642eb1b2db'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('knowledgedocument') as batch_op:
        batch_op.add_column(sa.Column('header_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('meta_json', sqlmodel.sql.sqltypes.AutoString(), nullable=True))
        batch_op.add_column(sa.Column('bibtex_key', sqlmodel.sql.sqltypes.AutoString(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('knowledgedocument') as batch_op:
        batch_op.drop_column('bibtex_key')
        batch_op.drop_column('meta_json')
        batch_op.drop_column('header_json')
