"""
Timestamp defaults must be callables.

`default=datetime.now(timezone.utc)` calls the function while the module is
being imported and stores the *result*, so every row inserted without an
explicit value got the process start time. Two visible consequences: ordering by
`created_at` was arbitrary, and — worse — `document_sharing.expires_at` used the
same shape, so every share link was created already expired.

`Column.default.is_callable` is exactly the property that distinguishes the bug
from the fix, and it needs no database.
"""
import time

import pytest

from app.db.tables.auth.auth import User
from app.db.tables.departments import Department
from app.db.tables.documents.document_sharing import DocumentSharing
from app.db.tables.documents.documents import Document
from app.db.tables.documents.notify import Notify
from app.db.tables.documents.permissions import Permission
from app.db.tables.documents.share_link import ShareLink
from app.db.tables.documents.shared import SharedDocument
from app.db.tables.documents.tags import Tag
from app.db.tables.documents.versions import DocumentVersion
from app.db.tables.tenants import Tenant

TIMESTAMP_DEFAULTS = [
    (Document, "created_at"),
    (User, "created_at"),
    (Department, "created_at"),
    (Tenant, "created_at"),
    (Notify, "created_at"),
    (Permission, "created_at"),
    (SharedDocument, "created_at"),
    (Tag, "created_at"),
    (DocumentVersion, "created_at"),
    # Already correct before this change — kept so a regression here is caught
    # with the rest.
    (ShareLink, "created_at"),
    # The one that expires rather than merely records.
    (DocumentSharing, "expires_at"),
]


@pytest.mark.parametrize(
    "model, column",
    TIMESTAMP_DEFAULTS,
    ids=[f"{m.__tablename__}.{c}" for m, c in TIMESTAMP_DEFAULTS],
)
def test_the_default_is_evaluated_per_row(model, column):
    default = model.__table__.c[column].default

    assert default is not None, f"{model.__tablename__}.{column} has no default"
    assert default.is_callable, (
        f"{model.__tablename__}.{column} was frozen at import time"
    )


@pytest.mark.parametrize(
    "model, column",
    TIMESTAMP_DEFAULTS,
    ids=[f"{m.__tablename__}.{c}" for m, c in TIMESTAMP_DEFAULTS],
)
def test_two_rows_get_two_different_timestamps(model, column):
    """The behaviour the property above stands for."""
    produce = model.__table__.c[column].default.arg

    first = produce(None)
    time.sleep(0.001)
    second = produce(None)

    assert second > first


def test_a_share_is_not_born_expired():
    """
    `expires_at` frozen at import meant every share's expiry was the moment the
    worker booted — already in the past for every share created after it.
    """
    from datetime import datetime, timedelta, timezone

    produce = DocumentSharing.__table__.c["expires_at"].default.arg

    assert produce(None) > datetime.now(timezone.utc) - timedelta(seconds=5)
