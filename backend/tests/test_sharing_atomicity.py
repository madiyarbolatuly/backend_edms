"""
Sharing a document with several people is all-or-nothing.

`create_share_records` committed, and the route called it once per recipient —
so an unknown recipient part-way down the list aborted the request with the
earlier ones already written and no way to undo them. Sharing a *folder* writes
one row per descendant, so a partial share could be hundreds of rows.

Two changes: every recipient is resolved before anything is written, and the
repository flushes instead of committing so the whole request is one transaction.
"""
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.api.routes.documents.document_sharing import share_link_document_by_id
from app.db.repositories.documents.document_sharing import SharedDocumentRepository
from app.db.tables.documents.shared import SharedDocument
from app.schemas.documents.document_sharing import SharingRequest

pytestmark = pytest.mark.asyncio


async def share_count(session) -> int:
    return (
        await session.execute(select(func.count()).select_from(SharedDocument))
    ).scalar_one()


class StubUsers:
    """Resolves anyone except the names in `unknown`."""

    def __init__(self, unknown=()):
        self.unknown = set(unknown)
        self.looked_up = []

    async def get_by_email_or_username(self, key):
        self.looked_up.append(key)
        if key in self.unknown:
            return None
        return type("U", (), {"id": f"id-of-{key}"})()


class TestCreateShareRecords:
    async def test_it_flushes_rather_than_commits(
        self, full_session, owner, make_full_document
    ):
        """
        The rows must be visible in the transaction but not yet durable, so the
        caller can still roll the whole share back.
        """
        doc = await make_full_document("смета.xlsx")
        repo = SharedDocumentRepository(full_session)

        await repo.create_share_records(
            owner_id=owner.id, doc_ids=[doc.id], shared_with_id="someone"
        )

        assert await share_count(full_session) == 1

        await full_session.rollback()

        # A commit inside the repository would have made this 1.
        assert await share_count(full_session) == 0

    async def test_a_row_is_written_per_document(
        self, full_session, owner, make_full_document
    ):
        a = await make_full_document("a.pdf")
        b = await make_full_document("b.pdf")
        repo = SharedDocumentRepository(full_session)

        await repo.create_share_records(
            owner_id=owner.id, doc_ids=[a.id, b.id], shared_with_id="someone"
        )

        assert await share_count(full_session) == 2


class TestRecipientsAreResolvedFirst:
    async def test_an_unknown_recipient_shares_with_nobody(
        self, full_session, full_repo, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx")
        users = StubUsers(unknown={"ghost@example.com"})
        share_repo = SharedDocumentRepository(full_session)

        import app.api.routes.documents.document_sharing as module

        original = module.AuthRepository
        module.AuthRepository = lambda _session: users
        try:
            with pytest.raises(HTTPException) as exc:
                await share_link_document_by_id(
                    file_id=doc.id,
                    share_request=SharingRequest(
                        share_to=["ok@example.com", "ghost@example.com"]
                    ),
                    metadata_repository=full_repo,
                    share_repo=share_repo,
                    user=owner,
                )
        finally:
            module.AuthRepository = original

        assert exc.value.status_code == 422
        # The regression: "ok@example.com" used to be committed before the
        # request reached the recipient that fails.
        assert await share_count(full_session) == 0

    async def test_every_recipient_is_checked_before_any_write(
        self, full_session, full_repo, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx")
        users = StubUsers(unknown={"ghost@example.com"})
        share_repo = SharedDocumentRepository(full_session)

        import app.api.routes.documents.document_sharing as module

        original = module.AuthRepository
        module.AuthRepository = lambda _session: users
        try:
            with pytest.raises(HTTPException):
                await share_link_document_by_id(
                    file_id=doc.id,
                    share_request=SharingRequest(
                        share_to=["a@example.com", "ghost@example.com", "c@example.com"]
                    ),
                    metadata_repository=full_repo,
                    share_repo=share_repo,
                    user=owner,
                )
        finally:
            module.AuthRepository = original

        # It stops at the bad one — but only after resolving, never after writing.
        assert users.looked_up[:2] == ["a@example.com", "ghost@example.com"]

    async def test_a_valid_share_still_works(
        self, full_session, full_repo, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx")
        users = StubUsers()
        share_repo = SharedDocumentRepository(full_session)

        import app.api.routes.documents.document_sharing as module

        original = module.AuthRepository
        module.AuthRepository = lambda _session: users
        try:
            result = await share_link_document_by_id(
                file_id=doc.id,
                share_request=SharingRequest(
                    share_to=["a@example.com", "b@example.com"]
                ),
                metadata_repository=full_repo,
                share_repo=share_repo,
                user=owner,
            )
        finally:
            module.AuthRepository = original

        assert "url" in result
        assert await share_count(full_session) == 2

    async def test_no_recipients_is_not_an_error(
        self, full_session, full_repo, owner, make_full_document
    ):
        """`share_to` is Optional; iterating it directly raised TypeError."""
        doc = await make_full_document("смета.xlsx")
        share_repo = SharedDocumentRepository(full_session)

        import app.api.routes.documents.document_sharing as module

        original = module.AuthRepository
        module.AuthRepository = lambda _session: StubUsers()
        try:
            result = await share_link_document_by_id(
                file_id=doc.id,
                share_request=SharingRequest(share_to=None),
                metadata_repository=full_repo,
                share_repo=share_repo,
                user=owner,
            )
        finally:
            module.AuthRepository = original

        assert "url" in result
        assert await share_count(full_session) == 0
