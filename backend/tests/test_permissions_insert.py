"""
Granting a user access to a document.

`_update_doc_user_access` built `insert(doc_user_access).values(doc_id=...)`,
but the column is `document_id` — so the statement raised
`CompileError: Unconsumed column names: doc_id` and per-user access grants never
worked at all. `_delete_access`, five lines below it, used the correct name, so
the two halves of the same feature disagreed.

Checked at compile level: `permissions` has foreign keys to `users` and
`documents`, and the test database in conftest only creates `documents`.
"""
import pytest
from sqlalchemy import insert
from sqlalchemy.exc import CompileError

from app.db.tables.documents.permissions import AccessLevel, doc_user_access


def render(stmt) -> str:
    return str(stmt.compile(compile_kwargs={"literal_binds": True}))


def test_the_association_table_names_its_column_document_id():
    assert "document_id" in doc_user_access.c
    assert "doc_id" not in doc_user_access.c


def test_the_old_spelling_would_not_compile():
    # The exact failure the fix removes.
    with pytest.raises(CompileError):
        render(insert(doc_user_access).values(doc_id=1, user_id="u1"))


def test_a_grant_compiles_with_every_required_column():
    # `access_level` is NOT NULL with no server default, so supplying only the
    # two ids would move the failure from CompileError to a NOT NULL violation.
    sql = render(
        insert(doc_user_access).values(
            document_id=1, user_id="u1", access_level=AccessLevel.read
        )
    )

    assert "document_id" in sql
    assert "user_id" in sql
    assert "access_level" in sql


def test_access_level_has_no_default_to_fall_back_on():
    column = doc_user_access.c.access_level
    assert column.nullable is False
    assert column.default is None and column.server_default is None
