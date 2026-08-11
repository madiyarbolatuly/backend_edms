"""
The bin, with Google-Drive semantics.

The reported problem: deleting one folder filled the trash with every file
inside it. `delete()` marks the target and its whole subtree identically, and
`bin_list()` returned every row with `status == deleted` — so a folder of 40
files produced 41 bin entries.

Now the bin lists only *trash roots*: a deleted row whose parent is not also
deleted. Restoring one brings its whole subtree back. There is no new column;
`parent_id` survives a soft delete, so "is my parent also in the bin" is the
whole test.
"""
import pytest

from app.db.tables.base_class import DocStatus
from app.db.repositories.documents.documents_metadata import MetadataRepository

pytestmark = pytest.mark.asyncio


async def bin_names(repo, owner) -> list[str]:
    listing = await repo.bin_list(owner=owner)
    return [d.name for d in listing["response"]]


class TestWhatTheBinShows:
    async def test_deleting_a_folder_puts_one_entry_in_the_bin(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document("Раздел", parent_id=folder.id, file_type="folder", size=None)
        await make_document("a.pdf", parent_id=folder.id)
        await make_document("deep.pdf", parent_id=sub.id)

        await repo.delete(document=folder.id, owner=owner)

        # This is the bug, stated: it used to be four.
        assert await bin_names(repo, owner) == ["Проект"]

    async def test_a_file_deleted_on_its_own_is_its_own_entry(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        doc = await make_document("смета.xlsx", parent_id=folder.id)

        await repo.delete(document=doc.id, owner=owner)

        # Its parent is alive, so it is a trash root in its own right.
        assert await bin_names(repo, owner) == ["смета.xlsx"]

    async def test_a_separately_trashed_file_is_absorbed_when_its_folder_goes(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        doc = await make_document("смета.xlsx", parent_id=folder.id)

        await repo.delete(document=doc.id, owner=owner)
        await repo.delete(document=folder.id, owner=owner)

        assert await bin_names(repo, owner) == ["Проект"]

    async def test_a_top_level_document_is_always_a_root(
        self, repo, owner, make_document
    ):
        doc = await make_document("смета.xlsx")

        await repo.delete(document=doc.id, owner=owner)

        assert await bin_names(repo, owner) == ["смета.xlsx"]

    async def test_two_separate_deletions_are_two_entries(
        self, repo, owner, make_document
    ):
        a = await make_document("Проект А", file_type="folder", size=None)
        await make_document("inside.pdf", parent_id=a.id)
        b = await make_document("смета.xlsx")

        await repo.delete(document=a.id, owner=owner)
        await repo.delete(document=b.id, owner=owner)

        assert sorted(await bin_names(repo, owner)) == ["Проект А", "смета.xlsx"]

    async def test_a_row_whose_parent_was_hard_deleted_still_shows(
        self, repo, owner, make_document, session
    ):
        """It must surface rather than vanish — otherwise it is unreachable."""
        from sqlalchemy import delete as sql_delete
        from app.db.tables.documents.documents import Document

        folder = await make_document("Проект", file_type="folder", size=None)
        doc = await make_document("смета.xlsx", parent_id=folder.id)
        await repo.delete(document=doc.id, owner=owner)

        await session.execute(sql_delete(Document).where(Document.id == folder.id))
        await session.flush()

        assert await bin_names(repo, owner) == ["смета.xlsx"]

    async def test_live_documents_are_not_in_the_bin(self, repo, owner, make_document):
        await make_document("живой.pdf")

        assert await bin_names(repo, owner) == []

    async def test_another_owners_trash_is_not_listed(
        self, repo, owner, make_document
    ):
        mine = await make_document("мой.pdf")
        theirs = await make_document("чужой.pdf", owner_id="someone-else")
        await repo.delete(document=mine.id, owner=owner)
        await repo.delete(document=theirs.id, owner=owner)

        assert await bin_names(repo, owner) == ["мой.pdf"]

    async def test_folders_are_listed_before_files(self, repo, owner, make_document):
        folder = await make_document("Папка", file_type="folder", size=None)
        doc = await make_document("файл.pdf")
        await repo.delete(document=doc.id, owner=owner)
        await repo.delete(document=folder.id, owner=owner)

        names = await bin_names(repo, owner)

        assert names.index("Папка") < names.index("файл.pdf")


class TestDeleteKeepsAnEarlierTrashStamp:
    async def test_an_already_trashed_child_keeps_its_own_deleted_at(
        self, repo, owner, make_document, session
    ):
        """
        Without the guard, deleting the folder restamps the whole subtree and
        the bin's "deleted at" column becomes a lie.
        """
        from sqlalchemy import select
        from app.db.tables.documents.documents import Document

        folder = await make_document("Проект", file_type="folder", size=None)
        doc = await make_document("смета.xlsx", parent_id=folder.id)

        await repo.delete(document=doc.id, owner=owner)
        first_stamp = (
            await session.execute(select(Document.deleted_at).where(Document.id == doc.id))
        ).scalar_one()

        await repo.delete(document=folder.id, owner=owner)
        second_stamp = (
            await session.execute(select(Document.deleted_at).where(Document.id == doc.id))
        ).scalar_one()

        assert second_stamp == first_stamp


class TestRestore:
    async def test_restoring_a_folder_brings_back_its_contents(
        self, repo, owner, make_document, session
    ):
        from sqlalchemy import select
        from app.db.tables.documents.documents import Document

        folder = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document("Раздел", parent_id=folder.id, file_type="folder", size=None)
        leaf = await make_document("deep.pdf", parent_id=sub.id)

        await repo.delete(document=folder.id, owner=owner)
        await repo.restore(doc_id=folder.id, owner=owner)

        rows = (await session.execute(select(Document))).scalars().all()
        assert all(r.deleted_at is None for r in rows)
        assert all(r.status != DocStatus.deleted for r in rows)
        assert {r.id for r in rows} == {folder.id, sub.id, leaf.id}

    async def test_a_restored_document_is_listed_again(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("смета.xlsx", parent_id=folder.id)

        await repo.delete(document=folder.id, owner=owner)
        await repo.restore(doc_id=folder.id, owner=owner)

        listing = await repo.doc_list(owner=owner, parent_id=folder.id)
        assert [d.name for d in listing["documents"]] == ["смета.xlsx"]
        assert await bin_names(repo, owner) == []

    async def test_restoring_a_nested_row_directly_is_refused(
        self, repo, owner, make_document
    ):
        """
        It would leave a live row under a deleted parent — invisible in every
        listing, and the state `_collect_purgeable` has to raise 409 over.
        """
        folder = await make_document("Проект", file_type="folder", size=None)
        doc = await make_document("смета.xlsx", parent_id=folder.id)
        await repo.delete(document=folder.id, owner=owner)

        with pytest.raises(Exception, match="родительскую"):
            await repo.restore(doc_id=doc.id, owner=owner)

    async def test_restoring_something_not_in_the_bin_is_a_404(
        self, repo, owner, make_document
    ):
        doc = await make_document("живой.pdf")

        with pytest.raises(Exception):
            await repo.restore(doc_id=doc.id, owner=owner)

    async def test_another_owners_document_cannot_be_restored(
        self, repo, owner, make_document
    ):
        theirs = await make_document("чужой.pdf", owner_id="someone-else")
        await repo.delete(document=theirs.id, owner=owner)

        with pytest.raises(Exception):
            await repo.restore(doc_id=theirs.id, owner=owner)

    async def test_restored_documents_are_reachable_by_colleagues(
        self, repo, owner, make_document, session
    ):
        """
        `delete()` discards the pre-delete status, so restore has to choose one.
        `private` would make a restored folder's contents unreadable to everyone
        but the owner, because `_get_instance` admits a row only when it is
        public or owned by the caller — and the importer writes everything as
        public. See `MetadataRepository.RESTORED_STATUS`.
        """
        from sqlalchemy import select
        from app.db.tables.documents.documents import Document

        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("смета.xlsx", parent_id=folder.id)

        await repo.delete(document=folder.id, owner=owner)
        await repo.restore(doc_id=folder.id, owner=owner)

        statuses = (await session.execute(select(Document.status))).scalars().all()
        assert set(statuses) == {MetadataRepository.RESTORED_STATUS}
        assert MetadataRepository.RESTORED_STATUS == DocStatus.public


class TestRoundTrip:
    async def test_delete_restore_delete_still_leaves_one_entry(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("a.pdf", parent_id=folder.id)

        await repo.delete(document=folder.id, owner=owner)
        await repo.restore(doc_id=folder.id, owner=owner)
        await repo.delete(document=folder.id, owner=owner)

        assert await bin_names(repo, owner) == ["Проект"]
