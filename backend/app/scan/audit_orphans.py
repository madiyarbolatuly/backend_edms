"""
Read-only audit: which `documents` rows have no file behind them?

Run this before deploying the `move_document` fix. That fix makes a move refuse
with 404 when the source file is missing, instead of silently rewriting the row
to a path with no file — which is honest, but it turns any *already* orphaned row
into one that cannot be moved until it is repaired. This tells you how many there
are, and why.

Two independent causes are separated in the report:

  1. Rows orphaned by the `move_document` bug itself. `file_path` was rewritten
     to the destination while the bytes stayed at the old location, and the old
     path was not recorded anywhere — so these are only recoverable by searching
     the filesystem for the file name.

  2. Rows whose `file_path` carries a duplicated storage prefix. The importer
     (`app/scan/scan_and_upload.py`) prefixes stored paths with ROOT_PREFIX
     ("1/1" in docker-compose.yml) while LOCAL_STORAGE_PATH already ends in
     `/1/1`, so the app resolves them to `uploads/1/1/1/1/<rel>`. These are
     repairable in bulk: strip the prefix.

Nothing is written. Usage:

    python app/scan/audit_orphans.py                 # summary
    python app/scan/audit_orphans.py --list 50       # plus example rows
    python app/scan/audit_orphans.py --csv out.csv   # every missing row
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.tables.base_class import DocStatus  # noqa: E402
from app.db.tables.documents.documents import Document  # noqa: E402

ROOT_PREFIX = os.environ.get("ROOT_PREFIX", "")


@dataclass
class Report:
    total: int = 0
    folders: int = 0
    resolved: int = 0
    fixable_by_stripping_prefix: int = 0
    missing: int = 0
    rows_fixable: list = field(default_factory=list)
    rows_missing: list = field(default_factory=list)


def classify(
    upload_root: Path, file_path: str | None, file_type: str, prefix: str
) -> tuple[str, str | None]:
    """
    Decide what one row's storage looks like.

    Returns `(category, suggested_path)` where category is one of
    "folder", "resolved", "prefix_duplicated" or "missing". Pure apart from the
    filesystem checks, so it can be tested without a database.
    """
    if file_type == "folder":
        return "folder", None

    rel = (file_path or "").lstrip("/")
    if not rel:
        return "missing", None

    if (upload_root / rel).is_file():
        return "resolved", None

    if prefix:
        as_posix = PurePosixPath(rel)
        if as_posix.is_relative_to(prefix):
            stripped = str(as_posix.relative_to(prefix))
            if (upload_root / stripped).is_file():
                return "prefix_duplicated", stripped

    return "missing", None


def audit(upload_root: Path, prefix: str) -> Report:
    report = Report()
    engine = create_engine(settings.sync_database_url)

    with engine.connect() as conn:
        rows = conn.execute(
            select(
                Document.id,
                Document.name,
                Document.file_path,
                Document.file_type,
                Document.tenant_id,
                Document.department_id,
            ).where(Document.status != DocStatus.deleted)
        )

        for row in rows:
            report.total += 1
            category, suggested = classify(
                upload_root, row.file_path, row.file_type, prefix
            )

            if category == "folder":
                # A folder needs no directory of its own — `create_folder` only
                # inserts a row. Counted, not judged.
                report.folders += 1
            elif category == "resolved":
                report.resolved += 1
            elif category == "prefix_duplicated":
                report.fixable_by_stripping_prefix += 1
                report.rows_fixable.append((row, suggested))
            else:
                report.missing += 1
                report.rows_missing.append(row)

    engine.dispose()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--list", type=int, default=0, metavar="N",
                        help="print up to N example rows from each category")
    parser.add_argument("--csv", metavar="PATH",
                        help="write every unresolved row to a CSV")
    parser.add_argument("--prefix", default=ROOT_PREFIX,
                        help='storage prefix to test for duplication (env ROOT_PREFIX)')
    args = parser.parse_args()

    upload_root = Path(settings.upload_dir)
    print(f"upload_dir : {upload_root}")
    print(f"prefix     : {args.prefix or '(none)'}")
    if not upload_root.is_dir():
        print(f"\n!! {upload_root} does not exist — every row will look orphaned.")
        print("   Run this where the storage volume is mounted.")

    report = audit(upload_root, args.prefix)

    print()
    print(f"documents (not deleted) : {report.total}")
    print(f"  folders               : {report.folders}  (no file expected)")
    print(f"  file present          : {report.resolved}")
    print(f"  fixable: prefix dupe  : {report.fixable_by_stripping_prefix}")
    print(f"  NO FILE FOUND         : {report.missing}")

    if report.fixable_by_stripping_prefix:
        print(
            f"\n{report.fixable_by_stripping_prefix} rows resolve once '{args.prefix}/' is\n"
            "stripped from file_path. These come from the importer and are repairable\n"
            "in bulk — but decide which convention is authoritative first, because\n"
            "changing file_path also changes what uniq_file considers a duplicate."
        )

    if report.missing:
        print(
            f"\n{report.missing} rows have no file under either convention. Moving any of\n"
            "them will now return 404 rather than silently corrupting the row further."
        )

    if args.list:
        for label, rows in (
            ("fixable by stripping the prefix", [r for r, _ in report.rows_fixable]),
            ("no file found", report.rows_missing),
        ):
            if not rows:
                continue
            print(f"\n-- {label} (first {min(args.list, len(rows))}) --")
            for row in rows[: args.list]:
                print(f"  id={row.id:<8} {row.file_path}")

    if args.csv:
        with open(args.csv, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                ["id", "name", "file_path", "tenant_id", "department_id",
                 "category", "suggested_file_path"]
            )
            for row, stripped in report.rows_fixable:
                writer.writerow([row.id, row.name, row.file_path, row.tenant_id,
                                 row.department_id, "prefix_duplicated", stripped])
            for row in report.rows_missing:
                writer.writerow([row.id, row.name, row.file_path, row.tenant_id,
                                 row.department_id, "missing", ""])
        print(f"\nWrote {args.csv}")

    # Non-zero when something needs attention, so this can gate a deploy.
    return 1 if (report.missing or report.fixable_by_stripping_prefix) else 0


if __name__ == "__main__":
    raise SystemExit(main())
