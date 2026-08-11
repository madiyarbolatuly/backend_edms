"""
Aggregated folder sizes.

A folder's size is the sum of everything whose `file_path` starts with the
folder's path. The prefix comes from a *column*, so the LIKE metacharacters in
it cannot be escaped in Python — a folder called `2024_Q1` matched `2024XQ1/...`
and reported its neighbour's bytes as its own. `_search_filter` in the same
module had always escaped correctly; the two now share `_escape_like`.
"""
import pytest

from app.db.repositories.documents.documents_metadata import MetadataRepository

pytestmark = pytest.mark.asyncio


async def sizes(repo, owner, folders):
    return await repo._folder_sizes(folders, owner)


async def test_a_folder_reports_the_bytes_beneath_it(repo, owner, make_document):
    folder = await make_document("Проект", file_type="folder", size=None, file_path="Проект")
    await make_document("a.pdf", parent_id=folder.id, size=100, file_path="Проект/a.pdf")
    await make_document("b.pdf", parent_id=folder.id, size=250, file_path="Проект/b.pdf")

    assert (await sizes(repo, owner, [folder]))[folder.id] == 350


async def test_nested_files_count_too(repo, owner, make_document):
    folder = await make_document("Проект", file_type="folder", size=None, file_path="Проект")
    sub = await make_document(
        "Раздел", parent_id=folder.id, file_type="folder", size=None,
        file_path="Проект/Раздел",
    )
    await make_document("deep.pdf", parent_id=sub.id, size=70, file_path="Проект/Раздел/deep.pdf")

    assert (await sizes(repo, owner, [folder]))[folder.id] == 70


async def test_an_underscore_is_matched_literally(repo, owner, make_document):
    """The regression: `_` is a single-character LIKE wildcard."""
    mine = await make_document("2024_Q1", file_type="folder", size=None, file_path="2024_Q1")
    await make_document("mine.pdf", parent_id=mine.id, size=100, file_path="2024_Q1/mine.pdf")

    neighbour = await make_document("2024XQ1", file_type="folder", size=None, file_path="2024XQ1")
    await make_document(
        "theirs.pdf", parent_id=neighbour.id, size=999, file_path="2024XQ1/theirs.pdf"
    )

    assert (await sizes(repo, owner, [mine]))[mine.id] == 100


async def test_a_percent_in_a_folder_name_is_matched_literally(repo, owner, make_document):
    """`%` matches any run of characters, so this folder used to absorb everything."""
    mine = await make_document("скидки 50%", file_type="folder", size=None, file_path="скидки 50%")
    await make_document("mine.pdf", parent_id=mine.id, size=10, file_path="скидки 50%/mine.pdf")

    other = await make_document("прочее", file_type="folder", size=None, file_path="прочее")
    await make_document("theirs.pdf", parent_id=other.id, size=999, file_path="прочее/theirs.pdf")

    assert (await sizes(repo, owner, [mine]))[mine.id] == 10


async def test_a_sibling_with_the_folder_name_as_a_prefix_is_excluded(
    repo, owner, make_document
):
    mine = await make_document("Отчёт", file_type="folder", size=None, file_path="Отчёт")
    await make_document("mine.pdf", parent_id=mine.id, size=5, file_path="Отчёт/mine.pdf")

    sibling = await make_document("Отчёт2024", file_type="folder", size=None, file_path="Отчёт2024")
    await make_document(
        "theirs.pdf", parent_id=sibling.id, size=999, file_path="Отчёт2024/theirs.pdf"
    )

    # The trailing "/" in the pattern is what separates these two.
    assert (await sizes(repo, owner, [mine]))[mine.id] == 5


async def test_folders_do_not_count_toward_a_size(repo, owner, make_document):
    folder = await make_document("Проект", file_type="folder", size=None, file_path="Проект")
    await make_document(
        "Раздел", parent_id=folder.id, file_type="folder", size=4096,
        file_path="Проект/Раздел",
    )

    assert (await sizes(repo, owner, [folder])).get(folder.id, 0) == 0


async def test_another_tenants_files_are_not_counted(repo, owner, make_document):
    folder = await make_document("Проект", file_type="folder", size=None, file_path="Проект")
    await make_document("mine.pdf", parent_id=folder.id, size=10, file_path="Проект/mine.pdf")
    await make_document(
        "theirs.pdf", parent_id=folder.id, size=999,
        file_path="Проект/theirs.pdf", tenant_id=999,
    )

    assert (await sizes(repo, owner, [folder]))[folder.id] == 10


async def test_an_empty_folder_has_no_row(repo, owner, make_document):
    folder = await make_document("Пусто", file_type="folder", size=None, file_path="Пусто")

    assert (await sizes(repo, owner, [folder])).get(folder.id, 0) == 0


class TestEscapeLike:
    def test_metacharacters_are_neutralised(self):
        assert MetadataRepository._escape_like("100%_x") == r"100\%\_x"

    def test_backslashes_are_escaped_first(self):
        # Otherwise the escapes added for % and _ would themselves be escaped.
        assert MetadataRepository._escape_like("a\\b") == "a\\\\b"

    def test_an_ordinary_name_is_unchanged(self):
        assert MetadataRepository._escape_like("отчёт.pdf") == "отчёт.pdf"
