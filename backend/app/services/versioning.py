# app/services/versioning.py
import time
from pathlib import Path

from app.core.config import settings


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def storage_root() -> Path:
    """
    Where documents actually live.

    This module used to define its own `UPLOAD_ROOT`, defaulting to
    `/var/docedms/uploads` and set by no `.env` and no compose file — a third
    storage root, unrelated to the `settings.upload_dir` the rest of the app
    reads and writes. Every edit saved from the browser was written to a
    directory nothing would ever read, so editing a document in OnlyOffice
    silently discarded the change.
    """
    return Path(settings.upload_dir)


def versions_dir() -> Path:
    """
    Snapshot storage, deliberately outside `upload_dir`.

    Under it, snapshots would be served by the `/files` static mount and swept
    into `documents` rows by the filesystem importer.
    """
    return Path(settings.upload_dir).parent / ".versions"


def resolve_within_storage(relative_path: str) -> Path:
    """
    Turn a stored `file_path` into an absolute path, refusing to escape.

    The callback's `doc_id` used to be interpolated straight into a filename,
    so a `doc_id` of `../../etc/foo` wrote outside the upload root.
    """
    root = storage_root().resolve()
    candidate = (root / str(relative_path).lstrip("/")).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Path escapes the storage root: {relative_path}")
    return candidate


def save_new_version(*, absolute_path: Path, doc_id: int | str, content: bytes) -> Path:
    """
    Snapshot the current file, then overwrite it with `content`.

    `absolute_path` is resolved and containment-checked by the caller — see
    `resolve_within_storage`.
    """
    ensure_dir(absolute_path.parent)

    snapshot_dir = versions_dir() / str(doc_id)
    ensure_dir(snapshot_dir)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    suffix = absolute_path.suffix or ""

    # Snapshot what is there now, so an overwrite is recoverable. A first-ever
    # save has nothing to snapshot.
    if absolute_path.is_file():
        (snapshot_dir / f"{stamp}{suffix}").write_bytes(absolute_path.read_bytes())

    absolute_path.write_bytes(content)
    return absolute_path
