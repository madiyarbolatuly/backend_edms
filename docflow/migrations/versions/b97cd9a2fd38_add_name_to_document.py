"""add name to document

Revision ID: b97cd9a2fd38
Revises: 0001_init
Create Date: 2025-07-11 13:59:52.729523

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b97cd9a2fd38'
down_revision: Union[str, None] = '0001_init'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
     op.add_column(
        "documents",
        sa.Column("file_type", sa.String(length=32), nullable=False,
                  server_default="file")
    )

def downgrade() -> None:
    op.drop_column("documents", "file_type")
