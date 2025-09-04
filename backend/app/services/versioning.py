# app/services/versioning.py
import os, time
from pathlib import Path

UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", "/var/docedms/uploads")

def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)

def current_file_path(doc_id: str, ext: str) -> Path:
    """
    Simple mapping: <UPLOAD_ROOT>/<doc_id>.<ext>
    Adjust if your storage layout differs.
    """
    return Path(UPLOAD_ROOT) / f"{doc_id}.{ext}"

def save_new_version(doc_id: str, ext: str, content: bytes) -> None:
    # Where the "live" file is stored
    live_path = current_file_path(doc_id, ext)
    ensure_dir(live_path.parent)

    # Save snapshot first
    versions_dir = Path(UPLOAD_ROOT) / ".versions" / doc_id
    ensure_dir(versions_dir)
    ts = time.strftime("%Y%m%d_%H%M%S")
    snapshot = versions_dir / f"{ts}.{ext}"
    snapshot.write_bytes(content)

    # Overwrite the current file with latest content
    live_path.write_bytes(content)
