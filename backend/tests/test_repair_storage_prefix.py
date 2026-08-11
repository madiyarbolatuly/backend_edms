"""
The one-off storage-prefix repair.

It rewrites `documents.file_path` on live data, so its decisions are tested as
pure functions rather than by running it. The rule it must never break: a row
whose file cannot be found under *either* convention is reported and left alone.
Rewriting a path we cannot verify would replace a known-broken row with a
differently-broken one and destroy the only record of where it pointed — the
same failure mode as the `move_document` bug.
"""
from pathlib import Path

import pytest

from app.scan.repair_storage_prefix import (
    duplicate_titles_at_root,
    find_container,
    plan_path_updates,
    strip_prefix,
)

PREFIX = "1/1"


class Row:
    """The subset of columns the planner selects."""

    def __init__(self, id, file_path, file_type="file", parent_id=None, title=None):
        self.id = id
        self.file_path = file_path
        self.file_type = file_type
        self.parent_id = parent_id
        self.title = title if title is not None else f"row-{id}"


@pytest.fixture
def storage(tmp_path) -> Path:
    (tmp_path / "Проект").mkdir()
    (tmp_path / "Проект" / "смета.xlsx").write_bytes(b"data")
    return tmp_path


class TestStripPrefix:
    def test_the_prefix_is_removed(self):
        assert strip_prefix("1/1/Проект/смета.xlsx", PREFIX) == "Проект/смета.xlsx"

    def test_a_leading_slash_is_tolerated(self):
        assert strip_prefix("/1/1/Проект", PREFIX) == "Проект"

    def test_a_path_without_the_prefix_is_left_alone(self):
        assert strip_prefix("Проект/смета.xlsx", PREFIX) is None

    def test_a_similar_prefix_is_not_matched(self):
        # `startswith` would strip this; path-relative comparison does not.
        assert strip_prefix("1/11/Проект", PREFIX) is None

    def test_the_container_path_itself_yields_nothing(self):
        # Stripping "1/1" from "1/1" leaves nothing — that row is Phase 2's job.
        assert strip_prefix("1/1", PREFIX) is None

    def test_an_empty_path_yields_nothing(self):
        assert strip_prefix("", PREFIX) is None
        assert strip_prefix(None, PREFIX) is None


class TestPlanPathUpdates:
    def test_a_file_whose_bytes_are_under_the_stripped_path_is_rewritten(self, storage):
        rows = [Row(1, "1/1/Проект/смета.xlsx")]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == [(1, "1/1/Проект/смета.xlsx", "Проект/смета.xlsx")]

    def test_a_file_that_already_resolves_is_skipped(self, storage):
        """This is what makes a second run a no-op."""
        rows = [Row(1, "Проект/смета.xlsx")]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == []
        assert plan.already_correct == 1

    def test_a_file_with_no_bytes_anywhere_is_reported_not_rewritten(self, storage):
        rows = [Row(1, "1/1/Проект/пропал.pdf")]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == []
        assert plan.unverifiable == [(1, "1/1/Проект/пропал.pdf")]

    def test_folders_are_rewritten_without_a_file_to_check(self, storage):
        """
        A folder has no bytes, but its path must be repaired too — `_folder_sizes`
        builds its LIKE pattern from `parent.file_path`, so a folder left
        prefixed reports a size of zero.
        """
        rows = [Row(1, "1/1/Проект", file_type="folder")]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == [(1, "1/1/Проект", "Проект")]

    def test_a_target_that_already_exists_is_skipped(self, storage):
        # `uniq_file` is (tenant, department, file_path) — this would abort the
        # transaction rather than just failing one row.
        rows = [
            Row(1, "Проект/смета.xlsx"),
            Row(2, "1/1/Проект/смета.xlsx"),
        ]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == []
        assert plan.collisions == [(2, "1/1/Проект/смета.xlsx", "Проект/смета.xlsx")]

    def test_two_rows_wanting_the_same_target_only_one_wins(self, storage):
        rows = [
            Row(1, "1/1/Проект", file_type="folder"),
            Row(2, "1/1/Проект", file_type="folder"),
        ]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert len(plan.updates) == 1
        assert len(plan.collisions) == 1

    def test_a_row_with_no_prefix_to_strip_is_counted_separately(self, storage):
        rows = [Row(1, "Другое/файл.pdf", file_type="folder")]

        plan = plan_path_updates(rows, storage, PREFIX)

        assert plan.updates == []
        assert plan.untouched == 1


class TestFindContainer:
    def test_the_container_is_found_by_path(self):
        rows = [
            Row(1, "1/1", file_type="folder", title="1"),
            Row(2, "1/1/Проект", file_type="folder", parent_id=1),
        ]

        assert find_container(rows, PREFIX).id == 1

    def test_a_misleading_title_does_not_matter(self):
        rows = [Row(1, "1/1", file_type="folder", title="что-угодно")]

        assert find_container(rows, PREFIX).id == 1

    def test_no_container_returns_none(self):
        rows = [Row(1, "Проект", file_type="folder")]

        assert find_container(rows, PREFIX) is None

    def test_two_candidates_return_none_rather_than_guessing(self):
        rows = [
            Row(1, "1/1", file_type="folder"),
            Row(2, "1/1", file_type="folder"),
        ]

        assert find_container(rows, PREFIX) is None

    def test_a_nested_folder_is_never_the_container(self):
        rows = [Row(1, "1/1", file_type="folder", parent_id=9)]

        assert find_container(rows, PREFIX) is None

    def test_a_file_is_never_the_container(self):
        rows = [Row(1, "1/1", file_type="file")]

        assert find_container(rows, PREFIX) is None


class TestDuplicateTitlesAtRoot:
    def test_a_clash_with_an_existing_root_folder_is_reported(self):
        rows = [
            Row(1, "1/1", file_type="folder", title="1"),
            Row(2, "1/1/Проект", file_type="folder", parent_id=1, title="Проект"),
            Row(3, "Проект", file_type="folder", parent_id=None, title="Проект"),
        ]

        assert duplicate_titles_at_root(rows, container_id=1) == ["Проект"]

    def test_no_clash_is_empty(self):
        rows = [
            Row(1, "1/1", file_type="folder", title="1"),
            Row(2, "1/1/Проект", file_type="folder", parent_id=1, title="Проект"),
        ]

        assert duplicate_titles_at_root(rows, container_id=1) == []

    def test_the_container_itself_is_not_counted_as_a_clash(self):
        rows = [
            Row(1, "1/1", file_type="folder", title="Проект"),
            Row(2, "1/1/Проект", file_type="folder", parent_id=1, title="Проект"),
        ]

        assert duplicate_titles_at_root(rows, container_id=1) == []
