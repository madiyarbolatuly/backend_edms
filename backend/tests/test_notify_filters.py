"""
Notification queries must filter on every clause they name.

The bug: `.where(Notify.user_id == user.id and Notify.id == n_id)`. Python's
`and` evaluates the left operand for truthiness and returns the right one, and a
SQLAlchemy expression is always truthy — so only the *last* clause survived.
`update_status` therefore filtered on the status alone and rewrote every
notification belonging to every user, then reported 404 because
`get_notification_by_id` — missing its own id filter — raised
MultipleResultsFound into a bare `except`.

Checked by capturing the statement each method issues and reading the compiled
SQL. `Notify.id` is a `postgresql.UUID` and `Notify.type` a `postgresql.ENUM`,
neither of which compiles on SQLite, so these cannot run against the test
database — but the WHERE clause is exactly what was wrong, and it is visible
here.
"""
from uuid import uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.db.repositories.documents.notify import NotifyRepo
from app.db.tables.base_class import NotifyEnum
from app.schemas.documents.bands import NotifyPatchStatus


class CapturingSession:
    """Records the statements it is handed and returns nothing useful."""

    def __init__(self):
        self.statements = []

    async def execute(self, stmt, *a, **kw):
        self.statements.append(stmt)
        return _EmptyResult()

    async def flush(self):
        pass

    def add(self, _obj):
        pass


class _EmptyResult:
    def scalar_one_or_none(self):
        return None

    def scalars(self):
        return self

    def all(self):
        return []


def sql_of(stmt) -> str:
    return str(stmt.compile(dialect=postgresql.dialect()))


@pytest.fixture
def captured():
    return CapturingSession()


@pytest.fixture
def repo(captured) -> NotifyRepo:
    return NotifyRepo(captured)


pytestmark = pytest.mark.asyncio


async def test_reading_one_notification_filters_on_both_the_user_and_the_id(
    repo, captured, owner
):
    n_id = uuid4()

    with pytest.raises(Exception):
        # No row comes back from the stub, so it 404s — after issuing the query.
        await repo.get_notification_by_id(n_id=n_id, user=owner)

    sql = sql_of(captured.statements[0])
    assert "notify.user_id" in sql
    assert "notify.id" in sql


async def test_listing_is_scoped_ordered_and_bounded(repo, captured, owner):
    await repo.get_notifications(user=owner)

    sql = sql_of(captured.statements[0])
    assert "notify.user_id" in sql
    # Unordered and unbounded, this returned a user's whole history in an
    # arbitrary order.
    assert "ORDER BY" in sql
    assert "LIMIT" in sql


async def test_marking_all_read_is_scoped_to_the_user(repo, captured, owner):
    await repo.mark_all_read(user=owner)

    sql = sql_of(captured.statements[0])
    assert "UPDATE notify" in sql
    assert "notify.user_id" in sql
    assert "notify.status" in sql


async def test_updating_one_notification_names_all_three_clauses(
    repo, captured, owner
):
    """The clause that used to be dropped is `notify.id` — without it this
    statement rewrote every row the user had."""
    n_id = uuid4()

    with pytest.raises(Exception):
        await repo.update_status(
            n_id=n_id,
            updated_status=NotifyPatchStatus(status=NotifyEnum.read),
            user=owner,
        )

    sql = sql_of(captured.statements[0])
    assert "UPDATE notify" in sql
    assert "notify.user_id" in sql
    assert "notify.id" in sql
    assert "notify.status" in sql


async def test_clearing_is_scoped_to_the_user(repo, captured, owner):
    await repo.clear_notification(user=owner)

    sql = sql_of(captured.statements[0])
    assert "DELETE FROM notify" in sql
    assert "notify.user_id" in sql


class TestNotificationSchema:
    def test_the_schema_names_the_columns_the_table_has(self):
        """
        It declared `receiver_id` and `notified_at`; the table has `user_id` and
        `created_at`. Validating a real row raised ValidationError, so
        `GET /v2/notifications` failed for any user who had one.
        """
        from app.schemas.documents.bands import Notification
        from app.db.tables.documents.notify import Notify

        columns = set(Notify.__table__.columns.keys())
        for field in Notification.model_fields:
            assert field in columns, field
