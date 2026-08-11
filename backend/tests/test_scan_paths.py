"""
What the scanner stores in `documents.file_path`.

That value is how the whole application finds a file, and it was wrong: compose
set ROOT_PREFIX="1/1" while LOCAL_STORAGE_PATH already ended in `/1/1`, so paths
were stored as `1/1/<rel>` and resolved to `uploads/1/1/1/1/<rel>` — every
download and preview 404'd.

These live here rather than beside the scanner because `scan_and_upload.py`
imports psycopg at module scope, so nothing in that file is importable by a test.
"""
from pathlib import PurePosixPath

import pytest

from app.scan.paths import normalise_prefix, rel_db_path

ROOT = "/usr/src/app/uploads/1/1"


class TestNormalisePrefix:
    @pytest.mark.parametrize("value", [None, "", "   ", "/", "//"])
    def test_nothing_means_no_prefix(self, value):
        assert normalise_prefix(value) == ""

    @pytest.mark.parametrize("value", ["1/1", "/1/1", "1/1/", "  /1/1/  "])
    def test_slashes_and_spaces_are_trimmed(self, value):
        assert normalise_prefix(value) == "1/1"


class TestRelDbPath:
    def test_a_path_under_the_scan_root_is_stored_relative_to_it(self):
        assert rel_db_path(f"{ROOT}/Projects-2025/смета.xlsx", ROOT) == (
            "Projects-2025/смета.xlsx"
        )

    def test_the_scan_root_itself_is_empty(self):
        assert rel_db_path(ROOT, ROOT) == ""

    def test_a_prefix_is_prepended_when_one_is_configured(self):
        assert rel_db_path(f"{ROOT}/смета.xlsx", ROOT, "archive") == (
            "archive/смета.xlsx"
        )

    def test_the_scan_root_with_a_prefix_is_the_prefix(self):
        assert rel_db_path(ROOT, ROOT, "archive") == "archive"

    def test_the_duplicated_prefix_is_no_longer_the_default(self):
        """
        The regression, named: with no ROOT_PREFIX set, a file directly under
        LOCAL_STORAGE_PATH must be stored as its own name — not `1/1/<name>`.
        """
        stored = rel_db_path(f"{ROOT}/смета.xlsx", ROOT)

        assert stored == "смета.xlsx"
        assert not stored.startswith("1/1/")

    def test_a_nested_path_keeps_every_level(self):
        assert rel_db_path(f"{ROOT}/a/b/c/d.pdf", ROOT) == "a/b/c/d.pdf"

    def test_separators_are_posix(self):
        stored = rel_db_path(f"{ROOT}/a/b/c.pdf", ROOT)

        assert "\\" not in stored
        assert PurePosixPath(stored).parts == ("a", "b", "c.pdf")

    def test_a_prefix_is_normalised_before_use(self):
        assert rel_db_path(f"{ROOT}/x.pdf", ROOT, "/archive/") == "archive/x.pdf"

    def test_a_path_outside_the_scan_root_is_rejected(self):
        # Better to fail loudly than to store something that cannot resolve.
        with pytest.raises(ValueError):
            rel_db_path("/etc/passwd", ROOT)

    def test_the_stored_path_resolves_back_under_the_storage_root(self, tmp_path):
        """The property that actually matters: storage_root / file_path is the file."""
        scan_root = tmp_path / "uploads" / "1" / "1"
        target = scan_root / "Projects-2025" / "смета.xlsx"
        target.parent.mkdir(parents=True)
        target.write_bytes(b"data")

        stored = rel_db_path(target, scan_root)

        assert (scan_root / stored).is_file()
