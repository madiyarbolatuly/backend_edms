"""
How long a share lasts when the sharer does not pick a date.

Three days, for both kinds of share. They used to disagree: a per-recipient
grant defaulted to a week, while a public link was stored with `expires_at`
NULL — which `share_links` reads as "never" — so the same "Поделиться" button
meant something different depending on which tab you were on, and the dialog
labelled the empty state "Без ограничения" in both.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.core.utils import default_share_expiry
from app.db.repositories.documents.document_sharing import SharedDocumentRepository

pytestmark = pytest.mark.asyncio

NOW = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)


def as_utc(value: datetime) -> datetime:
    """
    SQLite has no timezone-aware type, so a value written as UTC reads back
    naive. Postgres, where this actually runs, stores TIMESTAMPTZ and returns it
    aware. Normalising here keeps the assertions about the *instant* rather than
    about which database is under the test.
    """
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


class TestTheDefault:
    def test_it_is_three_days(self):
        assert settings.share_expiry_days == 3

    def test_the_helper_adds_that_many_days(self):
        assert default_share_expiry(NOW) == NOW + timedelta(days=3)

    def test_it_follows_the_setting(self, monkeypatch):
        monkeypatch.setattr(settings, "share_expiry_days", 10)

        assert default_share_expiry(NOW) == NOW + timedelta(days=10)

    def test_it_is_in_the_future(self):
        assert default_share_expiry() > datetime.now(timezone.utc)


class TestRecipientShares:
    async def test_a_share_without_a_date_expires_in_three_days(
        self, full_session, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx")
        repo = SharedDocumentRepository(full_session)

        before = datetime.now(timezone.utc)
        await repo.create_share_records(
            owner_id=owner.id, doc_ids=[doc.id], shared_with_id="someone"
        )

        from sqlalchemy import select
        from app.db.tables.documents.shared import SharedDocument

        share = (
            await full_session.execute(select(SharedDocument))
        ).scalars().one()

        # Was a week.
        assert share.expires_at is not None
        delta = as_utc(share.expires_at) - before
        assert timedelta(days=2, hours=23) < delta < timedelta(days=3, hours=1)

    async def test_an_explicit_date_is_respected(
        self, full_session, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx")
        repo = SharedDocumentRepository(full_session)
        chosen = datetime.now(timezone.utc) + timedelta(days=30)

        await repo.create_share_records(
            owner_id=owner.id, doc_ids=[doc.id],
            shared_with_id="someone", expires_at=chosen,
        )

        from sqlalchemy import select
        from app.db.tables.documents.shared import SharedDocument

        share = (await full_session.execute(select(SharedDocument))).scalars().one()

        assert as_utc(share.expires_at) == chosen

    async def test_every_document_in_a_shared_folder_gets_the_same_expiry(
        self, full_session, owner, make_full_document
    ):
        a = await make_full_document("a.pdf")
        b = await make_full_document("b.pdf")
        repo = SharedDocumentRepository(full_session)

        await repo.create_share_records(
            owner_id=owner.id, doc_ids=[a.id, b.id], shared_with_id="someone"
        )

        from sqlalchemy import select
        from app.db.tables.documents.shared import SharedDocument

        expiries = (
            await full_session.execute(select(SharedDocument.expires_at))
        ).scalars().all()

        assert len(set(expiries)) == 1
