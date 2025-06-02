"""empty message

Revision ID: 497a436f3a0d
Revises: 7f8629643798, add_is_archived_is_starred_columns
Create Date: 2025-05-30 05:09:08.436549

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '497a436f3a0d'
down_revision: Union[str, None] = ('7f8629643798', 'add_is_archived_is_starred_columns')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
