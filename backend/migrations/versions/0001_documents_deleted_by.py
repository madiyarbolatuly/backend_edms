"""documents.deleted_by — who put a row in the bin

The bin used to be scoped by `documents.owner_id`, but a user may trash any
document that is `public` within their tenant/department — including every row
the filesystem importer created, which all share one synthetic owner. Deleting
such a file removed it from the listings and put it in nobody's bin. The bin is
now scoped by this column.

Existing trashed rows keep NULL here; the repository falls back to `owner_id`
for those, so nothing already in a bin disappears.

Revision ID: 0001_documents_deleted_by
Revises:
Create Date: 2026-08-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_documents_deleted_by"
down_revision = None
branch_labels = None
depends_on = None


def _has_column(table: str, column: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    return column in {c["name"] for c in inspector.get_columns(table)}


def upgrade() -> None:
    # The app also reconciles this column on boot (`ensure_columns` in
    # app/db/models.py), so the migration has to tolerate it already being here.
    if _has_column("documents", "deleted_by"):
        return
    op.add_column("documents", sa.Column("deleted_by", sa.String(255), nullable=True))
    op.create_foreign_key(
        "fk_documents_deleted_by_users", "documents", "users", ["deleted_by"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_documents_deleted_by_users", "documents", type_="foreignkey")
    op.drop_column("documents", "deleted_by")
