"""add parent_id to document_metadata

Revision ID: 8f2d48135e28
Revises: e750bbb151f2
Create Date: 2025-05-26 13:53:55.961569

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8f2d48135e28'
down_revision: Union[str, None] = 'e750bbb151f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
