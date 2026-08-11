"""
One-off repair: strip a duplicated storage prefix from `documents.file_path`,
and remove the synthetic container folder the scanner used to create.

The scanner stored paths as `<ROOT_PREFIX>/<rel>` while `LOCAL_STORAGE_PATH`
already *was* `.../<ROOT_PREFIX>`, so the application resolved every file to
`uploads/1/1/1/1/<rel>` and downloads and previews 404'd. It also created a
top-level folder named after the scan directory (literally "1") wrapping the
whole library. `app/scan/paths.py` fixes this going forward; this repairs rows
already written.

    python app/scan/repair_storage_prefix.py --prefix 1/1              # dry run
    python app/scan/repair_storage_prefix.py --prefix 1/1 --apply

DRY RUN IS THE DEFAULT. `--apply` is required to write anything.

This is never imported by the application and is deliberately not a compose
service — a compose service is one `--profile` flag away from running at
startup, and this must only ever be run deliberately, against a backup.

Safe to abort: updates are applied in batches with an optimistic guard, and rows
that already resolve are skipped, so re-running finishes an interrupted run.

BEFORE RUNNING: back up the database, and keep the output of
`python app/scan/audit_orphans.py --csv orphans.csv` — that CSV is the only
record of the old paths.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, delete, func, select, update  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.db.tables.documents.documents import Document  # noqa: E402
from app.scan.audit_orphans import classify  # noqa: E402
from app.scan.paths import normalise_prefix  # noqa: E402

BATCH = 500


@dataclass
class PathPlan:
    """What Phase 1 intends to do."""
    updates: list[tuple[int, str, str]] = field(default_factory=list)   # (id, old, new)
    already_correct: int = 0
    unverifiable: list[tuple[int, str]] = field(default_factory=list)   # file has no bytes
    collisions: list[tuple[int, str, str]] = field(default_factory=list)
    untouched: int = 0                                                  # no prefix to strip


def strip_prefix(file_path: str | None, prefix: str) -> str | None:
    """
    `file_path` with `prefix/` removed, or None when it does not carry it.

    Pure string logic, used for folders. `PurePosixPath.is_relative_to` rather
    than `str.startswith` so `1/1x/...` is not mistaken for `1/1/...`.
    """
    rel = (file_path or "").lstrip("/")
    if not rel or not prefix:
        return None
    candidate = PurePosixPath(rel)
    if not candidate.is_relative_to(prefix):
        return None
    stripped = str(candidate.relative_to(prefix))
    # Never rewrite a path to nothing — that is the container row, and Phase 2
    # deals with it.
    return stripped if stripped not in ("", ".") else None


def plan_path_updates(rows, upload_root: Path, prefix: str) -> PathPlan:
    """
    Decide the rewrite for every row. Pure apart from `classify`'s filesystem
    checks, so it is testable without a database.

    Files are arbitrated by the filesystem via `classify`: a row whose bytes are
    found under the stripped path is rewritten; one that already resolves is
    left alone (this is what makes re-runs no-ops); one that resolves under
    neither convention is reported and NOT touched. Rewriting a path we cannot
    verify would replace a known-broken row with a differently-broken one and
    destroy the only record of where it pointed.

    Folders have no bytes to check, so they use `strip_prefix` alone — and they
    must be repaired, or `_folder_sizes`, which builds its LIKE pattern from
    `parent.file_path`, reports zero for every folder.
    """
    plan = PathPlan()
    taken = {r.file_path for r in rows if r.file_path}
    claimed: dict[str, int] = {}

    for row in rows:
        if row.file_type == "folder":
            stripped = strip_prefix(row.file_path, prefix)
            if stripped is None:
                plan.untouched += 1
                continue
            new_path = stripped
        else:
            category, suggested = classify(upload_root, row.file_path, row.file_type, prefix)
            if category == "resolved":
                plan.already_correct += 1
                continue
            if category == "prefix_duplicated":
                new_path = suggested
            else:  # "missing"
                if strip_prefix(row.file_path, prefix) is not None:
                    plan.unverifiable.append((row.id, row.file_path))
                else:
                    plan.untouched += 1
                continue

        # `uniq_file` is (tenant_id, department_id, file_path). Two rows wanting
        # the same target, or a target that already exists, would abort the
        # whole transaction — skip and report instead.
        if new_path in taken or new_path in claimed:
            plan.collisions.append((row.id, row.file_path, new_path))
            continue

        claimed[new_path] = row.id
        plan.updates.append((row.id, row.file_path, new_path))

    return plan


def find_container(rows, prefix: str):
    """
    The synthetic top-level folder, identified by PATH not title.

    Its title was `Path(ROOT_SCAN).name` — "1" for this deployment — which is
    too fragile to match on. Returns None unless exactly one row matches, so an
    ambiguous database stops the repair rather than guessing.
    """
    candidates = [
        r for r in rows
        if r.file_type == "folder"
        and r.parent_id is None
        and (r.file_path or "").strip("/") in {prefix, ""}
    ]
    return candidates[0] if len(candidates) == 1 else None


def duplicate_titles_at_root(rows, container_id: int) -> list[str]:
    """
    Titles that would collide at the top level once the container's children are
    re-parented.

    `uq_title_parent` is (title, parent_id) and Postgres treats NULLs as
    distinct, so this raises no constraint error — the risk is two identically
    titled folders silently sitting side by side at the root.
    """
    existing = {
        r.title for r in rows
        if r.parent_id is None and r.id != container_id
    }
    moving = [r.title for r in rows if r.parent_id == container_id]
    return sorted({t for t in moving if t in existing})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prefix", default="1/1",
                        help="the duplicated prefix to strip (default: 1/1)")
    parser.add_argument("--apply", action="store_true",
                        help="actually write; without it this is a dry run")
    parser.add_argument("--container-id", type=int, default=None,
                        help="remove this folder as the synthetic container")
    parser.add_argument("--allow-duplicate-titles", action="store_true",
                        help="proceed even if re-parenting creates duplicate root titles")
    parser.add_argument("--skip-container", action="store_true",
                        help="repair paths only; leave the container folder alone")
    args = parser.parse_args()

    prefix = normalise_prefix(args.prefix)
    if not prefix:
        print("--prefix must name a non-empty prefix, e.g. --prefix 1/1")
        return 2

    upload_root = Path(settings.upload_dir)
    mode = "APPLY" if args.apply else "DRY RUN"
    print(f"mode       : {mode}")
    print(f"upload_dir : {upload_root}")
    print(f"prefix     : {prefix}")
    if not upload_root.is_dir():
        print(f"\n!! {upload_root} does not exist. Every file would look missing, so\n"
              "   nothing could be verified. Run this where the storage is mounted.")
        return 2

    engine = create_engine(settings.sync_database_url)

    with engine.connect() as conn:
        # Deliberately includes trashed rows, unlike audit_orphans: a trashed
        # row with an unrepaired path 404s the moment it is restored.
        rows = conn.execute(
            select(
                Document.id, Document.title, Document.file_path,
                Document.file_type, Document.parent_id,
            )
        ).all()

    print(f"\nrows       : {len(rows)}")

    plan = plan_path_updates(rows, upload_root, prefix)
    print(f"  to rewrite         : {len(plan.updates)}")
    print(f"  already correct    : {plan.already_correct}")
    print(f"  no prefix to strip : {plan.untouched}")
    print(f"  unverifiable       : {len(plan.unverifiable)}  (left alone)")
    print(f"  collisions         : {len(plan.collisions)}  (skipped)")

    for doc_id, old, new in plan.collisions[:10]:
        print(f"    collision id={doc_id}: {old!r} -> {new!r} already exists")
    for doc_id, old in plan.unverifiable[:10]:
        print(f"    no file for id={doc_id}: {old!r}")

    container = None
    dupes: list[str] = []
    if not args.skip_container:
        if args.container_id is not None:
            container = next((r for r in rows if r.id == args.container_id), None)
            if container is None:
                print(f"\n!! --container-id {args.container_id} is not a document.")
                engine.dispose()
                return 2
        else:
            container = find_container(rows, prefix)

        if container is None:
            print("\ncontainer  : none found (or more than one) — leaving the tree alone.")
        else:
            children = [r for r in rows if r.parent_id == container.id]
            dupes = duplicate_titles_at_root(rows, container.id)
            print(f"\ncontainer  : id={container.id} title={container.title!r} "
                  f"path={container.file_path!r}")
            print(f"  children to re-parent to the root : {len(children)}")
            if dupes:
                print(f"  !! titles already at the root     : {', '.join(dupes)}")

    if not args.apply:
        print("\nDry run — nothing written. Re-run with --apply once this looks right.")
        engine.dispose()
        return 0

    if dupes and not args.allow_duplicate_titles:
        print("\nRefusing: re-parenting would put duplicate titles at the root.\n"
              "Rename them, or pass --allow-duplicate-titles.")
        engine.dispose()
        return 1

    written = 0
    with engine.begin() as conn:
        for start in range(0, len(plan.updates), BATCH):
            for doc_id, old, new in plan.updates[start:start + BATCH]:
                # Optimistic guard: a row someone changed underneath us is
                # skipped rather than clobbered.
                result = conn.execute(
                    update(Document)
                    .where(Document.id == doc_id)
                    .where(Document.file_path == old)
                    .values(file_path=new)
                )
                written += result.rowcount or 0
    print(f"\nRewrote {written} path(s).")

    if container is not None:
        with engine.begin() as conn:
            moved = conn.execute(
                update(Document)
                .where(Document.parent_id == container.id)
                .values(parent_id=None)
            ).rowcount or 0

            still_referenced = conn.execute(
                select(func.count()).select_from(Document)
                .where(Document.parent_id == container.id)
            ).scalar_one()

            if still_referenced:
                print(f"Left the container in place — {still_referenced} child(ren) remain.")
            else:
                conn.execute(delete(Document).where(Document.id == container.id))
                print(f"Re-parented {moved} folder(s) to the root and removed the container.")

    engine.dispose()
    print("\nDone. Verify with: python app/scan/audit_orphans.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
