"""
`MetadataRepository.doc_list` — the query behind every folder listing.

The regression these cover first: the query had no ORDER BY, so paging it with
OFFSET/LIMIT returned rows in whatever order the plan produced. Scrolling a
folder could show the same file twice and never show another at all.
"""
import pytest

from app.db.tables.base_class import DocStatus
from app.db.repositories.documents.documents_metadata import MetadataRepository

# `asyncio_mode = auto` in pytest.ini runs the coroutine tests; the synchronous
# ones in TestOrderByHelper are left alone.


async def names(result) -> list[str]:
    return [d.name for d in result["documents"]]


class TestOrdering:
    async def test_folders_come_before_files(self, repo, owner, make_document):
        await make_document("я-файл.pdf", parent_id=None)
        await make_document("а-папка", parent_id=None, file_type="folder", size=None)

        result = await repo.doc_list(owner=owner)

        # Folders first regardless of name — that is a layout rule, not a sort.
        assert await names(result) == ["а-папка", "я-файл.pdf"]

    async def test_folders_stay_first_when_sorting_descending(self, repo, owner, make_document):
        await make_document("а-файл.pdf")
        await make_document("я-папка", file_type="folder", size=None)

        result = await repo.doc_list(owner=owner, sort_dir="desc")

        assert (await names(result))[0] == "я-папка"

    async def test_names_sort_case_insensitively(self, repo, owner, make_document):
        for name in ["banana", "Apple", "cherry"]:
            await make_document(name)

        result = await repo.doc_list(owner=owner)

        # 'Apple' first — a case-sensitive sort would put every capital ahead.
        assert await names(result) == ["Apple", "banana", "cherry"]

    async def test_sort_by_size(self, repo, owner, make_document):
        await make_document("medium.pdf", size=500)
        await make_document("small.pdf", size=10)
        await make_document("large.pdf", size=9000)

        asc = await repo.doc_list(owner=owner, sort_by="size")
        desc = await repo.doc_list(owner=owner, sort_by="size", sort_dir="desc")

        assert await names(asc) == ["small.pdf", "medium.pdf", "large.pdf"]
        assert await names(desc) == ["large.pdf", "medium.pdf", "small.pdf"]

    async def test_sort_by_created_at(self, repo, owner, make_document):
        from datetime import datetime, timedelta, timezone

        base = datetime(2026, 1, 1, tzinfo=timezone.utc)
        await make_document("second.pdf", created_at=base + timedelta(days=1))
        await make_document("third.pdf", created_at=base + timedelta(days=2))
        await make_document("first.pdf", created_at=base)

        result = await repo.doc_list(owner=owner, sort_by="created_at")

        assert await names(result) == ["first.pdf", "second.pdf", "third.pdf"]

    async def test_unknown_sort_column_falls_back_to_name(self, repo, owner, make_document):
        await make_document("b.pdf")
        await make_document("a.pdf")

        # A hand-edited query string must not reach the ORDER BY clause.
        result = await repo.doc_list(owner=owner, sort_by="; DROP TABLE documents")

        assert await names(result) == ["a.pdf", "b.pdf"]

    async def test_order_is_total_when_names_collide(self, repo, owner, make_document):
        # Same name in the same folder is possible — uniqueness is on `title`.
        await make_document("copy.pdf", doc_id=30)
        await make_document("copy.pdf", doc_id=10)
        await make_document("copy.pdf", doc_id=20)

        result = await repo.doc_list(owner=owner)

        # `id` breaks the tie, so the order is defined rather than arbitrary.
        assert [d.id for d in result["documents"]] == [10, 20, 30]


class TestPaging:
    @pytest.fixture
    async def folder_of_25(self, make_document):
        folder = await make_document("Проект", file_type="folder", size=None)
        for i in range(25):
            await make_document(f"file-{i:03d}.pdf", parent_id=folder.id)
        return folder

    async def test_pages_partition_the_folder(self, repo, owner, folder_of_25):
        seen: list[str] = []
        for offset in range(0, 25, 10):
            page = await repo.doc_list(
                owner=owner, parent_id=folder_of_25.id, limit=10, offset=offset
            )
            seen.extend(await names(page))

        # The regression: every row exactly once, none skipped, none repeated.
        assert len(seen) == 25
        assert len(set(seen)) == 25
        assert seen == sorted(seen)

    async def test_total_count_is_the_folder_not_the_page(self, repo, owner, folder_of_25):
        page = await repo.doc_list(owner=owner, parent_id=folder_of_25.id, limit=10)

        assert len(page["documents"]) == 10
        # The listing header and the "load more" check both read this.
        assert page["total_count"] == 25

    async def test_offset_past_the_end_is_empty_not_an_error(self, repo, owner, folder_of_25):
        page = await repo.doc_list(owner=owner, parent_id=folder_of_25.id, limit=10, offset=100)

        assert page["documents"] == []
        assert page["total_count"] == 25


class TestScoping:
    async def test_lists_only_the_requested_folder(self, repo, owner, make_document):
        a = await make_document("A", file_type="folder", size=None)
        b = await make_document("B", file_type="folder", size=None)
        await make_document("in-a.pdf", parent_id=a.id)
        await make_document("in-b.pdf", parent_id=b.id)

        result = await repo.doc_list(owner=owner, parent_id=a.id)

        assert await names(result) == ["in-a.pdf"]

    async def test_root_listing_is_the_top_level_only(self, repo, owner, make_document):
        a = await make_document("A", file_type="folder", size=None)
        await make_document("nested.pdf", parent_id=a.id)

        result = await repo.doc_list(owner=owner)

        assert await names(result) == ["A"]

    async def test_only_folders_excludes_files(self, repo, owner, make_document):
        await make_document("Папка", file_type="folder", size=None)
        await make_document("file.pdf")

        result = await repo.doc_list(owner=owner, only_folders=True)

        assert await names(result) == ["Папка"]

    async def test_files_only_excludes_folders(self, repo, owner, make_document):
        await make_document("Папка", file_type="folder", size=None)
        await make_document("file.pdf")

        result = await repo.doc_list(owner=owner, files_only=True)

        assert await names(result) == ["file.pdf"]

    async def test_deleted_documents_are_hidden(self, repo, owner, make_document):
        await make_document("kept.pdf")
        await make_document("binned.pdf", status=DocStatus.deleted)

        result = await repo.doc_list(owner=owner)

        assert await names(result) == ["kept.pdf"]

    async def test_other_tenants_are_invisible(self, repo, owner, make_document):
        await make_document("ours.pdf")
        await make_document("theirs.pdf", tenant_id=999)

        result = await repo.doc_list(owner=owner)

        assert await names(result) == ["ours.pdf"]

    async def test_other_departments_are_invisible(self, repo, owner, make_document):
        await make_document("ours.pdf")
        await make_document("theirs.pdf", department_id=999)

        result = await repo.doc_list(owner=owner)

        assert await names(result) == ["ours.pdf"]


class TestSearch:
    async def test_matches_part_of_a_name(self, repo, owner, make_document):
        await make_document("Смета 2026.xlsx")
        await make_document("План этажа.pdf")

        result = await repo.doc_list(owner=owner, search="Смета")

        assert await names(result) == ["Смета 2026.xlsx"]

    async def test_matches_in_the_middle_of_a_name(self, repo, owner, make_document):
        await make_document("2026-smeta-final.xlsx")
        await make_document("2026-plan-final.pdf")

        result = await repo.doc_list(owner=owner, search="smeta")

        assert await names(result) == ["2026-smeta-final.xlsx"]

    async def test_is_case_insensitive(self, repo, owner, make_document):
        await make_document("Report.PDF")

        result = await repo.doc_list(owner=owner, search="report")

        # NB: ASCII deliberately. SQLite's `lower()` only folds ASCII, so a
        # Cyrillic case-insensitivity check would fail here while passing on
        # the Postgres the app actually runs on — a test that proves nothing
        # about the code. Case folding beyond ASCII is Postgres's job.
        assert await names(result) == ["Report.PDF"]

    async def test_counts_matches_not_the_folder(self, repo, owner, make_document):
        for i in range(10):
            await make_document(f"plan-{i}.pdf")
        await make_document("smeta.xlsx")

        result = await repo.doc_list(owner=owner, search="plan")

        # The count has to follow the filter, or "load more" never terminates.
        assert result["total_count"] == 10

    async def test_blank_search_is_no_filter(self, repo, owner, make_document):
        await make_document("a.pdf")
        await make_document("b.pdf")

        assert (await repo.doc_list(owner=owner, search="   "))["total_count"] == 2
        assert (await repo.doc_list(owner=owner, search=None))["total_count"] == 2

    async def test_percent_is_matched_literally(self, repo, owner, make_document):
        await make_document("скидка 50%.pdf")
        await make_document("обычный.pdf")

        # Unescaped, '%' is a LIKE wildcard and would match everything.
        result = await repo.doc_list(owner=owner, search="50%")

        assert await names(result) == ["скидка 50%.pdf"]

    async def test_underscore_is_matched_literally(self, repo, owner, make_document):
        await make_document("plan_a.pdf")
        await make_document("planXa.pdf")

        result = await repo.doc_list(owner=owner, search="plan_a")

        assert await names(result) == ["plan_a.pdf"]

    async def test_search_is_scoped_to_the_open_folder(self, repo, owner, make_document):
        a = await make_document("A", file_type="folder", size=None)
        b = await make_document("B", file_type="folder", size=None)
        await make_document("plan.pdf", parent_id=a.id)
        await make_document("plan.pdf", parent_id=b.id)

        result = await repo.doc_list(owner=owner, parent_id=a.id, search="plan")

        assert result["total_count"] == 1


class TestRecursive:
    async def test_walks_the_whole_subtree(self, repo, owner, make_document):
        root = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document("Раздел", parent_id=root.id, file_type="folder", size=None)
        await make_document("shallow.pdf", parent_id=root.id)
        await make_document("deep.pdf", parent_id=sub.id)

        result = await repo.doc_list(owner=owner, parent_id=root.id, recursive=True)

        # Compared as a set: this is about which rows come back, and the
        # ordering rules have their own tests.
        assert set(await names(result)) == {"Раздел", "deep.pdf", "shallow.pdf"}
        # The recursive term used to join the table to itself, which both
        # reached unrelated rows and repeated them through the UNION ALL.
        assert len(result["documents"]) == 3
        assert result["total_count"] == 3

    async def test_does_not_reach_outside_the_requested_subtree(
        self, repo, owner, make_document
    ):
        root = await make_document("Проект", file_type="folder", size=None)
        await make_document("inside.pdf", parent_id=root.id)
        elsewhere = await make_document("Другой", file_type="folder", size=None)
        await make_document("outside.pdf", parent_id=elsewhere.id)

        result = await repo.doc_list(owner=owner, parent_id=root.id, recursive=True)

        assert set(await names(result)) == {"inside.pdf"}

    async def test_search_reaches_matches_under_non_matching_folders(
        self, repo, owner, make_document
    ):
        root = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document("Раздел", parent_id=root.id, file_type="folder", size=None)
        await make_document("smeta.xlsx", parent_id=sub.id)

        # The folder in between does not match; filtering the walk itself would
        # cut the branch and lose the file underneath it.
        result = await repo.doc_list(
            owner=owner, parent_id=root.id, recursive=True, search="smeta"
        )

        assert await names(result) == ["smeta.xlsx"]

    async def test_recursive_pages_are_stable(self, repo, owner, make_document):
        root = await make_document("Проект", file_type="folder", size=None)
        sub = await make_document("Раздел", parent_id=root.id, file_type="folder", size=None)
        for i in range(12):
            await make_document(f"f-{i:02d}.pdf", parent_id=sub.id)

        first = await repo.doc_list(owner=owner, parent_id=root.id, recursive=True, limit=5)
        second = await repo.doc_list(
            owner=owner, parent_id=root.id, recursive=True, limit=5, offset=5
        )

        assert not set(await names(first)) & set(await names(second))


class TestRootScope:
    async def test_root_id_lists_that_projects_children(self, repo, owner, make_document):
        project = await make_document("Проект-1", file_type="folder", size=None)
        other = await make_document("Проект-2", file_type="folder", size=None)
        await make_document("mine.pdf", parent_id=project.id)
        await make_document("theirs.pdf", parent_id=other.id)

        # parent_id omitted means "the root of this project", not the library root.
        result = await repo.doc_list(owner=owner, root_id=project.id)

        assert await names(result) == ["mine.pdf"]

    async def test_root_id_search_is_confined_to_the_subtree(self, repo, owner, make_document):
        project = await make_document("Проект-1", file_type="folder", size=None)
        other = await make_document("Проект-2", file_type="folder", size=None)
        await make_document("plan.pdf", parent_id=project.id)
        await make_document("plan.pdf", parent_id=other.id)

        result = await repo.doc_list(
            owner=owner, root_id=project.id, recursive=True, search="plan"
        )

        assert result["total_count"] == 1


class TestOrderByHelper:
    """The clause builder, checked directly for the cases hardest to set up."""

    def test_always_ends_with_the_primary_key(self):
        for sort_by in ["name", "size", "created_at", None, "bogus"]:
            clauses = MetadataRepository._order_by(sort_by, "asc")
            rendered = str(clauses[-1])
            assert "documents.id" in rendered, sort_by

    def test_direction_applies_to_the_chosen_column_only(self):
        clauses = MetadataRepository._order_by("name", "desc")
        assert "DESC" in str(clauses[1])
        # The tiebreaker stays ascending so the order is reproducible.
        assert "DESC" not in str(clauses[-1])

    def test_folders_first_can_be_turned_off(self):
        with_folders = MetadataRepository._order_by("name", "asc")
        without = MetadataRepository._order_by("name", "asc", folders_first=False)
        assert len(with_folders) == len(without) + 1

    def test_search_filter_is_none_for_a_blank_term(self):
        assert MetadataRepository._search_filter(None) is None
        assert MetadataRepository._search_filter("") is None
        assert MetadataRepository._search_filter("   ") is None

    def test_search_filter_escapes_wildcards(self):
        clause = MetadataRepository._search_filter("100%_x")
        rendered = str(clause.compile(compile_kwargs={"literal_binds": True}))
        assert r"100\%\_x" in rendered
