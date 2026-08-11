"""
`GET /v2/filter` — document search.

It read `doc_list[f"documents of {user.username}"]` from a result whose only
keys are `documents` and `total_count`, so every request raised KeyError and
500'd. Because it never returned a 200, no client can depend on the old
response shape — which is why the filters below are a straight AND rather than
the previous list-of-lists.

The filter helpers had their own bug: `result.extend(doc for ...)` where `doc`
is a dict extends the list with the dict's *keys*, so a filtered search returned
field names.
"""
import pytest

from app.db.repositories.documents.document_organization import DocumentOrgRepository
from app.schemas.documents.documents_metadata import DocumentMetadataRead
from app.db.tables.base_class import DocStatus


def make_read(**over) -> DocumentMetadataRead:
    base = dict(
        id=1,
        tenant_id=1,
        department_id=1,
        owner_id="user-1",
        name="doc.pdf",
        file_path="/files/doc.pdf",
        created_at="2026-01-01T00:00:00Z",
        size=10,
        file_type="application/pdf",
        tags=[],
        status=DocStatus.public,
        parent_id=None,
    )
    base.update(over)
    return DocumentMetadataRead(**base)


@pytest.fixture
def org() -> DocumentOrgRepository:
    return DocumentOrgRepository()


pytestmark = pytest.mark.asyncio


class TestSearchDoc:
    async def test_no_filters_returns_everything(self, org):
        docs = [make_read(id=1), make_read(id=2)]

        assert await org.search_doc(docs=docs) == docs

    async def test_returns_documents_not_field_names(self, org):
        # The old implementation returned ["id", "tenant_id", ...] here.
        docs = [make_read(id=1, tags=["смета"])]

        result = await org.search_doc(docs=docs, tags="смета")

        assert result == docs
        assert isinstance(result[0], DocumentMetadataRead)

    async def test_filters_by_tag(self, org):
        docs = [make_read(id=1, tags=["смета"]), make_read(id=2, tags=["план"])]

        result = await org.search_doc(docs=docs, tags="смета")

        assert [d.id for d in result] == [1]

    async def test_several_tags_are_an_or_within_the_filter(self, org):
        docs = [
            make_read(id=1, tags=["смета"]),
            make_read(id=2, tags=["план"]),
            make_read(id=3, tags=["прочее"]),
        ]

        result = await org.search_doc(docs=docs, tags="смета, план")

        assert [d.id for d in result] == [1, 2]

    async def test_filters_by_file_type_using_the_extension(self, org):
        docs = [
            make_read(id=1, file_type="application/pdf"),
            make_read(id=2, file_type="image/png"),
        ]

        result = await org.search_doc(docs=docs, file_types="pdf")

        assert [d.id for d in result] == [1]

    async def test_folders_match_their_literal_file_type(self, org):
        docs = [make_read(id=1, file_type="folder"), make_read(id=2)]

        result = await org.search_doc(docs=docs, file_types="folder")

        assert [d.id for d in result] == [1]

    async def test_filters_by_status(self, org):
        docs = [
            make_read(id=1, status=DocStatus.public),
            make_read(id=2, status=DocStatus.archived),
        ]

        result = await org.search_doc(docs=docs, status="archived")

        assert [d.id for d in result] == [2]

    async def test_filters_combine_as_and(self, org):
        docs = [
            make_read(id=1, tags=["смета"], file_type="application/pdf"),
            make_read(id=2, tags=["смета"], file_type="image/png"),
            make_read(id=3, tags=["план"], file_type="application/pdf"),
        ]

        result = await org.search_doc(docs=docs, tags="смета", file_types="pdf")

        assert [d.id for d in result] == [1]

    async def test_a_filter_matching_nothing_is_an_empty_list(self, org):
        # Not None — the endpoint's contract is a list either way.
        assert await org.search_doc(docs=[make_read()], tags="отсутствует") == []

    async def test_documents_without_tags_are_not_matched(self, org):
        assert await org.search_doc(docs=[make_read(tags=None)], tags="смета") == []
