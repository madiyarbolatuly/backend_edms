"""
Storage-path helpers, deliberately free of dependencies.

`scan_and_upload.py` imports psycopg at module scope, so nothing in it can be
imported by a test. These two functions decide what goes into `documents.file_path`
— the value the whole application resolves files through — so they are the part
that most needs testing. Keeping them here lets both the scanner and the repair
script use one implementation.
"""
from __future__ import annotations

from pathlib import Path, PurePosixPath


def normalise_prefix(prefix: str | None) -> str:
    """
    A storage prefix, relative to LOCAL_STORAGE_PATH, with no leading or
    trailing slashes. Empty means "paths are relative to the storage root",
    which is the correct default.
    """
    return (prefix or "").strip().strip("/")


def rel_db_path(abs_path: Path | str, root_scan: Path | str, prefix: str = "") -> str:
    """
    The value to store in `documents.file_path` for a scanned file.

    Relative to the scan root, POSIX-separated, with `prefix` in front when one
    is configured.

    The prefix means "where the scan root sits *inside* LOCAL_STORAGE_PATH".
    It used to be derived as `Path(ROOT_SCAN).name` and was set to "1/1" in
    compose while LOCAL_STORAGE_PATH already ended in `/1/1` — so paths were
    stored as `1/1/<rel>` and resolved to `uploads/1/1/1/1/<rel>`, and every
    download 404'd. Scanning the storage root itself needs no prefix at all.
    """
    rel = Path(abs_path).relative_to(Path(root_scan))
    # `as_posix()` on the relative part, so a Windows-side scan stores forward
    # slashes like everything else.
    rel_posix = PurePosixPath(*rel.parts).as_posix() if rel.parts else ""

    prefix = normalise_prefix(prefix)
    if not prefix:
        return rel_posix
    return f"{prefix}/{rel_posix}" if rel_posix else prefix
