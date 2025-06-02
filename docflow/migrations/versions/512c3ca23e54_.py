"""empty message

Revision ID: 512c3ca23e54
Revises: 497a436f3a0d, add_archived_starred_columns
Create Date: 2025-05-30 06:53:46.207108

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '512c3ca23e54'
down_revision: Union[str, None] = ('497a436f3a0d', 'add_archived_starred_columns')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
