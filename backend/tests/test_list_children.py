"""
`GET /v2/children/{parent_id}` — what is inside a folder.

The scoping bug: `list_children` read `getattr(self, "tenant_id", None)`, an
attribute `MetadataRepository.__init__` never sets, so it always fell through to
taking the tenant and department **from the folder being requested**. Any
authenticated user could therefore walk any tenant's entire library by
incrementing an integer, and the folder-download ZIP — which uses the same
method — inherited it.

The cross-tenant tests here fail against the pre-fix code.
"""
import pytest

from app.db.tables.base_class import DocStatus

pytestmark = pytest.mark.asyncio


async def names(rows) -> set[str]:
    return {r.name for r in rows}


class TestScoping:
    async def test_lists_the_direct_children_of_a_folder(
        self, repo, owner, make_document
    ):
        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("a.pdf", parent_id=folder.id)
        await make_document("b.pdf", parent_id=folder.id)
        await make_document("elsewhere.pdf")

        rows = await repo.list_children(user=owner, parent_id=folder.id)

        assert await names(rows) == {"a.pdf", "b.pdf"}

    async def test_another_tenants_folder_reads_as_empty(
        self, repo, owner, other_owner, make_document
    ):
        folder = await make_document(
            "Чужой проект", file_type="folder", size=None,
            tenant_id=999, department_id=999,
        )
        await make_document(
            "secret.pdf", parent_id=folder.id, tenant_id=999, department_id=999,
        )

        # Empty rather than 404: telling "does not exist" apart from "not yours"
        # is the enumeration oracle this defect was.
        assert await repo.list_children(user=owner, parent_id=folder.id) == []

    async def test_your_own_folder_is_still_readable_by_you(
        self, repo, other_owner, make_document
    ):
        """The mirror of the test above — proves the scoping is not just 'deny'."""
        folder = await make_document(
            "Их проект", file_type="folder", size=None,
            tenant_id=999, department_id=999,
        )
        await make_document(
            "theirs.pdf", parent_id=folder.id, tenant_id=999, department_id=999,
        )

        rows = await repo.list_children(user=other_owner, parent_id=folder.id)

        assert await names(rows) == {"theirs.pdf"}

    async def test_another_departments_folder_reads_as_empty(
        self, repo, owner, make_document
    ):
        folder = await make_document(
            "Другой отдел", file_type="folder", size=None, department_id=42
        )
        await make_document("secret.pdf", parent_id=folder.id, department_id=42)

        assert await repo.list_children(user=owner, parent_id=folder.id) == []

    async def test_a_child_belonging_to_another_tenant_is_not_listed(
        self, repo, owner, make_document
    ):
        """A row planted under one of *your* folders must not leak either."""
        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("mine.pdf", parent_id=folder.id)
        await make_document("theirs.pdf", parent_id=folder.id, tenant_id=999)

        rows = await repo.list_children(user=owner, parent_id=folder.id)

        assert await names(rows) == {"mine.pdf"}

    async def test_an_unknown_id_is_empty_not_an_error(self, repo, owner):
        assert await repo.list_children(user=owner, parent_id=987654) == []

    async def test_no_parent_id_is_empty(self, repo, owner):
        assert await repo.list_children(user=owner, parent_id=None) == []


class TestDeletedRows:
    async def test_trashed_children_are_hidden(self, repo, owner, make_document):
        folder = await make_document("Проект", file_type="folder", size=None)
        await make_document("kept.pdf", parent_id=folder.id)
        await make_document("binned.pdf", parent_id=folder.id, status=DocStatus.deleted)

        rows = await repo.list_children(user=owner, parent_id=folder.id)

        # These used to be listed, and were written into the folder ZIP.
        assert await names(rows) == {"kept.pdf"}

    async def test_a_trashed_folder_is_not_browsable(self, repo, owner, make_document):
        folder = await make_document(
            "Удалённый", file_type="folder", size=None, status=DocStatus.deleted
        )
        await make_document("inside.pdf", parent_id=folder.id)

        assert await repo.list_children(user=owner, parent_id=folder.id) == []


class TestRecursive:
    async def test_walks_the_whole_subtree(self, repo, owner, make_document):
        root = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document(
            "Раздел", parent_id=root.id, file_type="folder", size=None
        )
        await make_document("shallow.pdf", parent_id=root.id)
        await make_document("deep.pdf", parent_id=sub.id)

        rows = await repo.list_children(user=owner, parent_id=root.id, recursive=True)

        assert await names(rows) == {"Раздел", "shallow.pdf", "deep.pdf"}

    async def test_recursive_does_not_reach_another_tenant(
        self, repo, owner, make_document
    ):
        root = await make_document(
            "Чужой", file_type="folder", size=None, tenant_id=999, department_id=999
        )
        await make_document(
            "secret.pdf", parent_id=root.id, tenant_id=999, department_id=999
        )

        assert await repo.list_children(user=owner, parent_id=root.id, recursive=True) == []

    async def test_recursive_hides_trashed_rows(self, repo, owner, make_document):
        root = await make_document("Проект", file_type="folder", size=None)
        await make_document("kept.pdf", parent_id=root.id)
        await make_document("binned.pdf", parent_id=root.id, status=DocStatus.deleted)

        rows = await repo.list_children(user=owner, parent_id=root.id, recursive=True)

        assert await names(rows) == {"kept.pdf"}
