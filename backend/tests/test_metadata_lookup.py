"""
`MetadataRepository.get_doc` — lookup by file name.

It ran the query, called `result.fetchall()` (consuming the cursor), then
`result.scalar_one_or_none()` on the exhausted result — so it returned `None`
for every document that exists. Its one caller, `patch(..., is_owner=False)`,
then handed that `None` to `_execute_update`, which dereferences `.id`.
"""
import pytest

from app.db.tables.base_class import DocStatus

pytestmark = pytest.mark.asyncio


async def test_an_existing_document_is_returned(repo, make_document):
    await make_document("смета.xlsx")

    found = await repo.get_doc(filename="смета.xlsx")

    assert found is not None
    assert found.name == "смета.xlsx"


async def test_a_missing_document_is_none(repo):
    assert await repo.get_doc(filename="нет-такого.pdf") is None


async def test_a_repeated_name_returns_one_row_rather_than_raising(repo, make_document):
    # `name` is deliberately not unique — the same file name is legitimate in
    # two folders — so `scalar_one_or_none()` would raise MultipleResultsFound
    # here. `.first()` is the correct shape for this query.
    await make_document("отчёт.pdf", parent_id=None)
    await make_document("отчёт.pdf", parent_id=None)

    found = await repo.get_doc(filename="отчёт.pdf")

    assert found is not None
    assert found.name == "отчёт.pdf"


async def test_a_trashed_document_is_not_returned(repo, make_document):
    await make_document("удалён.pdf", status=DocStatus.deleted)
    # `get_doc` filters on deleted_at, so set it the way `delete()` does.
    from datetime import datetime, timezone
    from sqlalchemy import update
    from app.db.tables.documents.documents import Document

    await repo.session.execute(
        update(Document).values(deleted_at=datetime.now(timezone.utc))
    )

    assert await repo.get_doc(filename="удалён.pdf") is None
