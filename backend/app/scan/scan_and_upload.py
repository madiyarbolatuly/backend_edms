#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Idempotent filesystem → documents loader.

Handles these uniqueness variants (tries them in order):
  A) (tenant_id, department_id, file_path)          -- your "uniq_file"
  B) (title, parent_id)                              -- your "uq_title_parent"
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
ROOT_PREFIX   = os.environ.get("ROOT_PREFIX") or Path(ROOT_SCAN).name

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
            with psycopg.connect(dbname=DB_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT) as conn:
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
    rel = abs_path.relative_to(ROOT_SCAN)
    db_path = f"{ROOT_PREFIX}/{str(rel).replace('\\', '/')}"
    return db_path.replace("//", "/")

def _insert_base_params(file_type, title, name, status, file_path, parent_id, file_hash):
    return (
        TENANT_ID, DEPARTMENT_ID, OWNER_ID,
        file_type, str(uuid.uuid4()), title, name,
        status, file_path, file_hash, datetime.now(timezone.utc), parent_id
    )

def _sql_base():
    return """
        INSERT INTO documents(
          tenant_id, department_id, owner_id,
          file_type, document_number, title, name,
          status, file_path, is_archived, is_favourited,
          file_hash, created_at, parent_id
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,false,false,%s,%s,%s
        )
    """

def upsert_document(cur, *, file_type, title, name, status, file_path, parent_id, file_hash=None) -> int:
    """
    Try three conflict targets in order:
      A) (tenant_id, department_id, file_path)
      B) (title, parent_id)
      C) (tenant_id, department_id, file_type, file_path)
    Using SAVEPOINTs so a conflict doesn't abort the whole transaction.
    """
    params = _insert_base_params(file_type, title, name, status, file_path, parent_id, file_hash)

    # A) match "uniq_file" → (tenant_id, department_id, file_path)
    sql_A = _sql_base() + """
        ON CONFLICT (tenant_id, department_id, file_path) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            parent_id = EXCLUDED.parent_id,
            file_type = EXCLUDED.file_type,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash)
        RETURNING id;
    """

    # B) match uq_title_parent → (title, parent_id)
    sql_B = _sql_base() + """
        ON CONFLICT (title, parent_id) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            file_path = EXCLUDED.file_path,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash)
        RETURNING id;
    """

    # C) match (tenant_id, department_id, file_type, file_path)
    sql_C = _sql_base() + """
        ON CONFLICT (tenant_id, department_id, file_type, file_path) DO UPDATE
        SET title     = EXCLUDED.title,
            name      = EXCLUDED.name,
            status    = EXCLUDED.status,
            parent_id = EXCLUDED.parent_id,
            file_hash = COALESCE(EXCLUDED.file_hash, documents.file_hash)
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

def process_directory(cur, parent_id: int, fs_path: Path):
    for entry in fs_path.iterdir():
        name = entry.name

        if entry.is_dir():
            if should_skip_dir(name):
                continue
            db_path = norm_rel_db_path(entry)
            folder_id = upsert_document(
                cur,
                file_type="folder",
                title=name, name=name, status="public",
                file_path=db_path, parent_id=parent_id,
                file_hash=None
            )
            process_directory(cur, folder_id, entry)
            continue

        # Files
        if name in EXCLUDE_FILES:
            continue

        try:
            file_hash = get_file_hash(entry) if entry.is_file() else None
        except Exception:
            file_hash = None  # hashing errors shouldn't stop scanning

        db_path = norm_rel_db_path(entry)
        upsert_document(
            cur,
            file_type="file",
            title=name, name=name, status="public",
            file_path=db_path, parent_id=parent_id,
            file_hash=file_hash
        )

def get_or_create_root(cur) -> int:
    """
    Reuse existing root row if present (parent_id IS NULL).
    """
    cur.execute(
        """
        SELECT id FROM documents
        WHERE tenant_id=%s AND department_id=%s
          AND file_type='folder' AND title=%s AND parent_id IS NULL
        LIMIT 1;
        """,
        (TENANT_ID, DEPARTMENT_ID, ROOT_PREFIX),
    )
    row = cur.fetchone()
    if row:
        return row[0]
    return upsert_document(
        cur,
        file_type="folder",
        title=ROOT_PREFIX, name=ROOT_PREFIX, status="public",
        file_path=f"{ROOT_PREFIX}", parent_id=None, file_hash=None
    )

def main():
    root_dir = Path(ROOT_SCAN)
    if not root_dir.is_dir():
        raise SystemExit(f"ROOT_SCAN not found: {ROOT_SCAN}")

    print(f"📂 Scanning: {ROOT_SCAN}  →  DB path prefix: '{ROOT_PREFIX}'")

    wait_for_postgres()

    with psycopg.connect(dbname=DB_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT) as conn:
        with conn.cursor() as cur:
            root_id = get_or_create_root(cur)
            process_directory(cur, root_id, root_dir)
        conn.commit()

    print(f"✔ Indexed {ROOT_SCAN} as '{ROOT_PREFIX}' (no duplicates; junk skipped)")

if __name__ == "__main__":
    main()

