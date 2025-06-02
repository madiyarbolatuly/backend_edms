"""Add is_archived and is_starred columns to document_metadata

Revision ID: add_archived_starred_columns
Revises: e750bbb151f2
Create Date: 2025-05-30
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'add_archived_starred_columns'
down_revision = 'e750bbb151f2'
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('document_metadata', sa.Column('is_archived', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('document_metadata', sa.Column('is_starred', sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column('document_metadata', 'is_archived')
    op.drop_column('document_metadata', 'is_starred')
