"""
The pre-deploy orphan audit.

This script gates the `move_document` rollout, so its classification has to be
right — a false "resolved" would let the deploy proceed over data that the new
hard 404 makes un-movable.
"""
from pathlib import Path

import pytest

from app.scan.audit_orphans import classify

PREFIX = "1/1"


@pytest.fixture
def storage(tmp_path) -> Path:
    (tmp_path / "Проект").mkdir()
    (tmp_path / "Проект" / "смета.xlsx").write_bytes(b"data")
    return tmp_path


def test_a_folder_needs_no_file(storage):
    assert classify(storage, "Проект", "folder", PREFIX) == ("folder", None)


def test_a_file_that_is_where_the_row_says_it_is(storage):
    assert classify(storage, "Проект/смета.xlsx", "file", PREFIX) == ("resolved", None)


def test_a_leading_slash_is_tolerated(storage):
    # `file_path` is stored relative, but rows written by different paths have
    # differed on the leading slash.
    assert classify(storage, "/Проект/смета.xlsx", "file", PREFIX)[0] == "resolved"


def test_a_duplicated_storage_prefix_is_reported_as_repairable(storage):
    """
    The importer prefixes paths with ROOT_PREFIX ("1/1") while
    LOCAL_STORAGE_PATH already ends in /1/1, so these resolve one level too deep.
    """
    category, suggested = classify(storage, "1/1/Проект/смета.xlsx", "file", PREFIX)

    assert category == "prefix_duplicated"
    assert suggested == "Проект/смета.xlsx"


def test_a_missing_file_is_missing(storage):
    assert classify(storage, "Проект/нет.pdf", "file", PREFIX) == ("missing", None)


def test_a_prefixed_path_whose_file_is_also_absent_is_missing(storage):
    # Carrying the prefix is not on its own enough to call it repairable.
    assert classify(storage, "1/1/Проект/нет.pdf", "file", PREFIX)[0] == "missing"


def test_an_empty_path_is_missing(storage):
    assert classify(storage, "", "file", PREFIX) == ("missing", None)
    assert classify(storage, None, "file", PREFIX) == ("missing", None)


def test_a_path_that_merely_starts_with_the_prefix_characters_is_not_stripped(storage):
    """`11/x` starts with "1" but is not under "1/1" — `is_relative_to` is what
    makes that distinction, rather than `str.startswith`."""
    (storage / "11").mkdir()
    (storage / "11" / "x.pdf").write_bytes(b"d")

    assert classify(storage, "11/x.pdf", "file", PREFIX)[0] == "resolved"


def test_no_prefix_configured_means_no_repair_suggestion(storage):
    assert classify(storage, "1/1/Проект/смета.xlsx", "file", "")[0] == "missing"


def test_a_directory_at_the_path_does_not_count_as_the_file(storage):
    # `is_file()`, not `exists()` — a directory where a file should be is still
    # a broken row.
    assert classify(storage, "Проект", "file", PREFIX)[0] == "missing"
