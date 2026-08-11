"""
Permanently removing documents from the bin.

Both `perm_delete_a_doc` and `empty_bin` issued a bare `DELETE` on `documents`.
Two ways that fails on Postgres:

  * a trashed folder's trashed descendants still point at it through
    `parent_id`, so deleting only the requested row violates the self-FK;
  * `document_versions`, `shared_documents`, `share_links` and `permissions` all
    reference `documents.id`. `Document.children` declares
    `cascade="all, delete"`, but that is an ORM cascade and a Core `delete()`
    statement bypasses it.

Caveat on coverage: SQLite does not enforce foreign keys unless
`PRAGMA foreign_keys=ON`, and enabling it here would fail on the FKs to tables
this fixture does not create. These tests therefore prove the right *rows* are
removed in the right *order*; they cannot reproduce the ForeignKeyViolation
itself. That one is Postgres-only.
"""
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

from app.db.tables.base_class import DocStatus
from app.db.tables.documents.documents import Document
from app.db.tables.documents.share_link import ShareLink
from app.db.tables.documents.shared import SharedDocument
from app.db.tables.documents.versions import DocumentVersion

pytestmark = pytest.mark.asyncio

TRASHED = {"status": DocStatus.deleted, "deleted_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}


async def count(session, model) -> int:
    return (await session.execute(select(func.count()).select_from(model))).scalar_one()


async def ids(session) -> set[int]:
    return set((await session.execute(select(Document.id))).scalars().all())


class TestPermDeleteOneDocument:
    async def test_a_trashed_file_is_removed(
        self, full_repo, full_session, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx", **TRASHED)

        await full_repo.perm_delete_a_doc(document=doc.id, owner=owner)

        assert await ids(full_session) == set()

    async def test_a_folder_takes_its_trashed_children_with_it(
        self, full_repo, full_session, owner, make_full_document
    ):
        folder = await make_full_document("Проект", file_type="folder", **TRASHED)
        sub = await make_full_document(
            "Раздел", parent_id=folder.id, file_type="folder", **TRASHED
        )
        await make_full_document("deep.pdf", parent_id=sub.id, **TRASHED)

        await full_repo.perm_delete_a_doc(document=folder.id, owner=owner)

        # Deleting only the requested row left the descendants pointing at a
        # parent that no longer existed.
        assert await ids(full_session) == set()

    async def test_a_folder_holding_a_restored_item_is_refused(
        self, full_repo, full_session, owner, make_full_document
    ):
        folder = await make_full_document("Проект", file_type="folder", **TRASHED)
        # `restore()` restores one row by name and does not touch its ancestors,
        # so a live child under a trashed parent is reachable.
        await make_full_document("восстановлен.pdf", parent_id=folder.id)

        with pytest.raises(Exception, match="восстановленные"):
            await full_repo.perm_delete_a_doc(document=folder.id, owner=owner)

        assert len(await ids(full_session)) == 2

    async def test_dependents_are_purged_first(
        self, full_repo, full_session, owner, make_full_document
    ):
        doc = await make_full_document("смета.xlsx", **TRASHED)
        full_session.add_all([
            DocumentVersion(
                id=1, document_id=doc.id, version_number=1, file_path="v1"
            ),
            ShareLink(id=1, token="tok", document_id=doc.id, created_by=owner.id),
            SharedDocument(
                id=1, document_id=doc.id, shared_by=owner.id,
                shared_with="someone", token="t2", filename="смета.xlsx",
            ),
        ])
        await full_session.flush()

        await full_repo.perm_delete_a_doc(document=doc.id, owner=owner)

        assert await count(full_session, DocumentVersion) == 0
        assert await count(full_session, ShareLink) == 0
        assert await count(full_session, SharedDocument) == 0

    async def test_a_document_that_is_not_in_the_bin_is_not_deleted(
        self, full_repo, full_session, owner, make_full_document
    ):
        doc = await make_full_document("живой.pdf")

        with pytest.raises(Exception):
            await full_repo.perm_delete_a_doc(document=doc.id, owner=owner)

        assert await ids(full_session) == {doc.id}

    async def test_another_owners_document_is_not_deleted(
        self, full_repo, full_session, owner, make_full_document
    ):
        doc = await make_full_document("чужой.pdf", owner_id="someone-else", **TRASHED)

        with pytest.raises(Exception):
            await full_repo.perm_delete_a_doc(document=doc.id, owner=owner)

        assert await ids(full_session) == {doc.id}


class TestEmptyBin:
    async def test_removes_a_whole_trashed_subtree(
        self, full_repo, full_session, owner, make_full_document
    ):
        folder = await make_full_document("Проект", file_type="folder", **TRASHED)
        await make_full_document("a.pdf", parent_id=folder.id, **TRASHED)
        await make_full_document("b.pdf", **TRASHED)

        result = await full_repo.empty_bin(owner=owner)

        assert await ids(full_session) == set()
        assert result["deleted"] == 3
        assert result["skipped"] == []

    async def test_live_documents_are_untouched(
        self, full_repo, full_session, owner, make_full_document
    ):
        keep = await make_full_document("живой.pdf")
        await make_full_document("удалён.pdf", **TRASHED)

        await full_repo.empty_bin(owner=owner)

        assert await ids(full_session) == {keep.id}

    async def test_a_folder_with_a_restored_child_is_skipped_not_fatal(
        self, full_repo, full_session, owner, make_full_document
    ):
        """One awkward folder must not stop the rest of the bin from emptying."""
        folder = await make_full_document("Проблемный", file_type="folder", **TRASHED)
        restored = await make_full_document("восстановлен.pdf", parent_id=folder.id)
        other = await make_full_document("обычный.pdf", **TRASHED)

        result = await full_repo.empty_bin(owner=owner)

        remaining = await ids(full_session)
        assert other.id not in remaining          # the rest was emptied
        assert {folder.id, restored.id} <= remaining
        assert result["skipped"] == ["Проблемный"]

    async def test_another_owners_bin_is_untouched(
        self, full_repo, full_session, owner, make_full_document
    ):
        mine = await make_full_document("мой.pdf", **TRASHED)
        theirs = await make_full_document(
            "чужой.pdf", owner_id="someone-else", **TRASHED
        )

        await full_repo.empty_bin(owner=owner)

        assert await ids(full_session) == {theirs.id}
        assert mine.id not in await ids(full_session)

    async def test_an_empty_bin_is_not_an_error(self, full_repo, owner):
        result = await full_repo.empty_bin(owner=owner)

        assert result == {"deleted": 0, "skipped": []}
