"""
`GET /v2/metadata/folders` — the folder picker's source.

It had no filters whatsoever: not tenant, not department, not deleted. Every
caller received the complete folder tree of every tenant in the database. The
`owner` parameter was already there and simply went unused, and the code said so
— `# add tenant / ACL filters here as you do elsewhere`.
"""
import pytest

from app.db.tables.base_class import DocStatus

pytestmark = pytest.mark.asyncio


async def folder_names(result) -> set[str]:
    return {f["name"] for f in result["folders"]}


async def test_lists_your_folders(repo, owner, make_document):
    await make_document("Проекты-2025", file_type="folder", size=None)
    await make_document("Проекты-2026", file_type="folder", size=None)

    assert await folder_names(await repo.list_folders(owner=owner)) == {
        "Проекты-2025",
        "Проекты-2026",
    }


async def test_files_are_not_folders(repo, owner, make_document):
    await make_document("Проекты-2025", file_type="folder", size=None)
    await make_document("смета.xlsx")

    assert await folder_names(await repo.list_folders(owner=owner)) == {"Проекты-2025"}


async def test_another_tenants_folders_are_not_listed(repo, owner, make_document):
    await make_document("Мой проект", file_type="folder", size=None)
    await make_document(
        "Чужой проект", file_type="folder", size=None, tenant_id=999, department_id=999
    )

    assert await folder_names(await repo.list_folders(owner=owner)) == {"Мой проект"}


async def test_another_departments_folders_are_not_listed(repo, owner, make_document):
    await make_document("Мой проект", file_type="folder", size=None)
    await make_document("Другой отдел", file_type="folder", size=None, department_id=42)

    assert await folder_names(await repo.list_folders(owner=owner)) == {"Мой проект"}


async def test_trashed_folders_are_not_listed(repo, owner, make_document):
    await make_document("Живой", file_type="folder", size=None)
    await make_document(
        "Удалённый", file_type="folder", size=None, status=DocStatus.deleted
    )

    # Offering a deleted folder as a move destination would resurrect it.
    assert await folder_names(await repo.list_folders(owner=owner)) == {"Живой"}


async def test_the_other_tenant_still_sees_their_own(repo, other_owner, make_document):
    await make_document("Мой проект", file_type="folder", size=None)
    await make_document(
        "Их проект", file_type="folder", size=None, tenant_id=999, department_id=999
    )

    assert await folder_names(await repo.list_folders(owner=other_owner)) == {
        "Их проект"
    }


async def test_roots_come_before_their_children(repo, owner, make_document):
    root = await make_document("Проекты-2025", file_type="folder", size=None)
    await make_document("Объект А", parent_id=root.id, file_type="folder", size=None)

    listed = [f["name"] for f in (await repo.list_folders(owner=owner))["folders"]]

    assert listed.index("Проекты-2025") < listed.index("Объект А")
