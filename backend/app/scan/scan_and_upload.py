#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Idempotent filesystem → documents loader.

Handles these uniqueness variants (tries them in order):
  A) (tenant_id, department_id, file_path)          -- your "uniq_file"
  B) (title, parent_id)                             -- your "uq_title_parent"
  C) (tenant_id, department_id, file_type, file_path)

Skips junk files (Thumbs.db, desktop.ini, .DS_Store).
Reuses the root row across re-runs.
"""

import os
import hashlib
import uuid
import time
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from psycopg.errors import OperationalError, UniqueViolation

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from app.scan.paths import normalise_prefix, rel_db_path  # noqa: E402

# ── DB config (env-overridable)
DB_NAME   = os.environ.get("POSTGRES_DB", "docflow_db")
USER      = os.environ.get("POSTGRES_USER", "postgres")
PASSWORD  = os.environ.get("POSTGRES_PASSWORD", "postgres")
HOST      = os.environ.get("POSTGRES_HOST", "postgres")
PORT      = os.environ.get("POSTGRES_PORT", "5432")

TENANT_ID     = int(os.environ.get("TENANT_ID", "1"))
DEPARTMENT_ID = int(os.environ.get("DEPARTMENT_ID", "1"))
OWNER_ID      = os.environ.get("OWNER_ID", "c17ba46f-b4b0-473c-ac93-cb10cfed0f7e")  # ← per your request

# ── Scan roots
ROOT_SCAN_RAW = os.environ.get("ROOT_SCAN", "/mnt/Projects-2025").strip()
ROOT_SCAN     = str(Path(ROOT_SCAN_RAW).resolve())
# Where the scan root sits *inside* LOCAL_STORAGE_PATH. Empty — the default —
# means the scan root IS the storage root, which is the usual case.
#
# This used to default to `Path(ROOT_SCAN).name`, and compose set it to "1/1"
# while LOCAL_STORAGE_PATH already ended in `/1/1`. Every path was stored as
# `1/1/<rel>` and resolved to `uploads/1/1/1/1/<rel>`, so downloads and previews
# 404'd. See app/scan/repair_storage_prefix.py for repairing rows written that way.
ROOT_PREFIX   = normalise_prefix(os.environ.get("ROOT_PREFIX"))

# ── Hashing
HASH_FILES  = os.environ.get("HASH_FILES", "true").lower() == "true"

# ── Skip noise
EXCLUDE_FILES = {"Thumbs.db", "desktop.ini", ".DS_Store"}
EXCLUDE_DIRS  = {
    d.strip() for d in os.environ.get(
        "EXCLUDE_DIRS",
        "$RECYCLE.BIN, System Volume Information, .git, .idea, node_modules"
    ).split(",")
}

def wait_for_postgres(retries=10, delay=3):
    for i in range(retries):
        try:
            with psycopg.connect(
                dbname=DB_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            print("✅ Postgres is ready!")
            return
        except OperationalError as e:
            print(f"⏳ Waiting for Postgres... ({i+1}/{retries}) {e}")
            time.sleep(delay)
    raise SystemExit("❌ Postgres is not ready after retries")

def get_file_hash(path: Path):
    if not HASH_FILES:
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def norm_rel_db_path(abs_path: Path) -> str:
    """See `app/scan/paths.py` — kept as a thin alias so call sites read the same."""
    return rel_db_path(abs_path, ROOT_SCAN, ROOT_PREFIX)

def _insert_base_params(file_type, title, name, status, file_path, parent_id, file_hash, size):
    return (
        TENANT_ID, DEPARTMENT_ID, OWNER_ID,
        file_type, str(uuid.uuid4()), title, name,
        status, file_path, file_hash, size, datetime.now(timezone.utc), parent_id
    )

def _sql_base():
    return """
        INSERT INTO documents(
          tenant_id, department_id, owner_id,
          file_type, document_number, title, name,
          status, file_path, is_archived, is_favourited,
          file_hash, size, created_at, parent_id
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,false,false,%s,%s,%s,%s
        )
    """

def upsert_document(cur, *, file_type, title, name, status, file_path, parent_id, file_hash=None, size=None) -> int:
    """
    Try three conflict targets in order:
      A) (tenant_id, department_id, file_path)
      B) (title, parent_id)
      C) (tenant_id, department_id, file_type, file_path)
    Using SAVEPOINTs so a conflict doesn't abort the whole transaction.
    """
    params = _insert_base_params(file_type, title, name, status, file_path, parent_id, file_hash, size)

    # A) match "uniq_file" → (tenant_id, department_id, file_path)
    sql_A = _sql_base() + """
        ON CONFLICT (tenant_id, department_id, file_path) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            parent_id = EXCLUDED.parent_id,
            file_type = EXCLUDED.file_type,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash),
            size      = EXCLUDED.size
        RETURNING id;
    """

    # B) match uq_title_parent → (title, parent_id)
    sql_B = _sql_base() + """
        ON CONFLICT (title, parent_id) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            file_path = EXCLUDED.file_path,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash),
            size      = EXCLUDED.size
        RETURNING id;
    """

    # C) match (tenant_id, department_id, file_type, file_path)
    sql_C = _sql_base() + """
        ON CONFLICT (tenant_id, department_id, file_type, file_path) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            parent_id = EXCLUDED.parent_id,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash),
            size      = EXCLUDED.size
        RETURNING id;
    """

    for idx, sql in enumerate((sql_A, sql_B, sql_C), start=1):
        cur.execute(f"SAVEPOINT sp_upsert_{idx};")
        try:
            cur.execute(sql, params)
            doc_id = cur.fetchone()[0]
            cur.execute(f"RELEASE SAVEPOINT sp_upsert_{idx};")
            return doc_id
        except UniqueViolation:
            cur.execute(f"ROLLBACK TO SAVEPOINT sp_upsert_{idx};")
            cur.execute(f"RELEASE SAVEPOINT sp_upsert_{idx};")
            continue

    # If we get here, something else is uniquely conflicting.
    raise UniqueViolation("Upsert failed on all known unique keys for path/title")

def should_skip_dir(name: str) -> bool:
    n = name.strip()
    return n in EXCLUDE_DIRS or n.startswith(".Trash") or n == "" or n == "lost+found"

def process_directory(cur, parent_id: int | None, fs_path: Path, seen_paths: set[str]):
    """`parent_id=None` is the top level — the storage root has no document row."""
    for entry in fs_path.iterdir():
        name = entry.name

        if entry.is_dir():
            if should_skip_dir(name):
                continue
            db_path = norm_rel_db_path(entry)
            seen_paths.add(db_path)
            folder_id = upsert_document(
                cur,
                file_type="folder",
                title=name, name=name, status="public",
                file_path=db_path, parent_id=parent_id,
                file_hash=None, size=None
            )
            process_directory(cur, folder_id, entry, seen_paths)
            continue

        # Files
        if name in EXCLUDE_FILES:
            continue

        try:
            file_hash = get_file_hash(entry) if entry.is_file() else None
        except Exception:
            file_hash = None  # hashing errors shouldn't stop scanning

        try:
            file_size = entry.stat().st_size
        except OSError:
            file_size = None

        db_path = norm_rel_db_path(entry)
        seen_paths.add(db_path)
        upsert_document(
            cur,
            file_type="file",
            title=name, name=name, status="public",
            file_path=db_path, parent_id=parent_id,
            file_hash=file_hash, size=file_size
        )

# NOTE: there is deliberately no `get_or_create_root` any more.
#
# The scanner used to synthesise a top-level folder to hang everything off,
# titled `Path(ROOT_SCAN).name` — with ROOT_SCAN=/usr/src/app/uploads/1/1 that is
# a folder literally called "1" — whose file_path was ROOT_PREFIX, a storage
# detail leaking into the document tree. It also pushed every real folder down a
# level, which is why the frontend grew a "containers and their children" model
# to compensate. The directories inside ROOT_SCAN are now top-level documents,
# which is what the navigation shows.


def load_existing_paths(cur) -> set[str]:
    """
    All paths in DB for this tenant/department under this ROOT_PREFIX.

    With an empty prefix — the normal case — that is every row for the
    tenant/department. Filtering on `file_path = '' OR LIKE '/%'` would match
    nothing and silently disable `delete_stale_paths`.
    """
    if ROOT_PREFIX:
        cur.execute(
            """
            SELECT file_path
            FROM documents
            WHERE tenant_id=%s AND department_id=%s
              AND (file_path = %s OR file_path LIKE %s)
            """,
            (TENANT_ID, DEPARTMENT_ID, ROOT_PREFIX, f"{ROOT_PREFIX}/%"),
        )
    else:
        cur.execute(
            """
            SELECT file_path
            FROM documents
            WHERE tenant_id=%s AND department_id=%s
            """,
            (TENANT_ID, DEPARTMENT_ID),
        )
    return {row[0] for row in cur.fetchall()}

def delete_stale_paths(cur, existing_paths: set[str], seen_paths: set[str]):
    """
    Remove documents that no longer exist in filesystem.

    Rules:
      - Only paths in existing_paths but not in seen_paths are considered stale.
      - Never delete documents that are referenced from shared_documents.
      - Never delete a document that still has children (folders/files) in documents.
      - Delete in iterations from leaves up to avoid parent_id FK violations.
    """
    stale_paths = existing_paths - seen_paths
    if not stale_paths:
        return

    remaining_paths = set(stale_paths)
    total_deleted = 0
    total_shared_protected = 0

    while remaining_paths:
        # Load current info for remaining stale paths
        cur.execute(
            """
            SELECT d.id,
                   d.file_path,
                   EXISTS (
                       SELECT 1 FROM shared_documents s
                       WHERE s.document_id = d.id
                   ) AS is_shared,
                   EXISTS (
                       SELECT 1 FROM documents c
                       WHERE c.parent_id = d.id
                   ) AS has_children
            FROM documents d
            WHERE d.tenant_id = %s
              AND d.department_id = %s
              AND d.file_path = ANY(%s)
            """,
            (TENANT_ID, DEPARTMENT_ID, list(remaining_paths)),
        )
        rows = cur.fetchall()
        if not rows:
            break

        leaf_ids: list[int] = []
        leaf_paths: list[str] = []
        newly_protected_shared = 0

        for doc_id, path, is_shared, has_children in rows:
            # if shared – never delete, drop from remaining
            if is_shared:
                remaining_paths.discard(path)
                newly_protected_shared += 1
                continue
            # if has children – cannot delete in this iteration
            if has_children:
                continue
            # leaf, not shared – safe to delete now
            leaf_ids.append(doc_id)
            leaf_paths.append(path)

        total_shared_protected += newly_protected_shared

        if not leaf_ids:
            # No more deletable leaves among remaining_paths:
            # stop to avoid infinite loop.
            break

        cur.execute(
            """
            DELETE FROM documents
            WHERE id = ANY(%s)
            """,
            (leaf_ids,),
        )
        total_deleted += len(leaf_ids)

        # Remove deleted paths from remaining set
        for p in leaf_paths:
            remaining_paths.discard(p)

    if total_deleted:
        print(f"🧹 Removed {total_deleted} stale records from DB")
    if total_shared_protected:
        print(
            f"🔒 Skipped {total_shared_protected} stale records that are shared "
            f"(kept to preserve shared links)"
        )
    if remaining_paths:
        # These are stale by path, but still have children that are not deletable
        # (e.g. weird DB state); we leave them to satisfy FK constraints.
        print(f"⚠ Left {len(remaining_paths)} stale records because they still have children")

def main():
    root_dir = Path(ROOT_SCAN)
    if not root_dir.is_dir():
        raise SystemExit(f"ROOT_SCAN not found: {ROOT_SCAN}")

    print(f"📂 Scanning: {ROOT_SCAN}  →  DB path prefix: '{ROOT_PREFIX}'")

    wait_for_postgres()

    with psycopg.connect(
        dbname=DB_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT
    ) as conn:
        with conn.cursor() as cur:
            existing_paths = load_existing_paths(cur)

            seen_paths: set[str] = set()

            # No synthetic container: the directories inside ROOT_SCAN become
            # top-level documents, so the navigation starts where the storage
            # does.
            process_directory(cur, None, root_dir, seen_paths)

            # удалить всё, чего больше нет в файловой системе,
            # но не трогаем shared и не ломаем parent_id FK
            delete_stale_paths(cur, existing_paths, seen_paths)

        conn.commit()

    scope = f"'{ROOT_PREFIX}'" if ROOT_PREFIX else "the storage root"
    print(f"✔ Indexed {ROOT_SCAN} as {scope} (no duplicates; junk skipped)")

if __name__ == "__main__":
    main()

