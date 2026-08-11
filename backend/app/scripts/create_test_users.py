"""
Create a set of test users, one per role, for manual testing.

Idempotent: a user that already exists is left alone, so this is safe to re-run.
Nothing is deleted.

    python app/scripts/create_test_users.py                 # the three roles
    python app/scripts/create_test_users.py --with-outsider # + a second tenant
    python app/scripts/create_test_users.py --password 'Своя1234'
    python app/scripts/create_test_users.py --delete        # remove them again

The accounts it creates are obviously-test ones (`test.admin` and friends). They
are NOT for a public deployment — see the warning printed at the end.

`--with-outsider` adds a user in a *different* tenant, which is what you need to
check that one tenant cannot see another's folders. It creates that tenant and a
department for it if they are missing.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

from app.api.dependencies.auth_utils import get_hashed_password  # noqa: E402
from app.core.config import settings  # noqa: E402
from app.db.tables.auth.auth import User  # noqa: E402
from app.db.tables.departments import Department  # noqa: E402
from app.db.tables.documents.documents import Document  # noqa: E402
from app.db.tables.tenants import Tenant  # noqa: E402

DEFAULT_PASSWORD = "Test1234!"

# The tenant/department the existing data lives in — see backup.sql.
HOME_TENANT = 1
HOME_DEPARTMENT = 1

TEST_USERS = [
    ("test.admin",  "test.admin@example.com",  "admin"),
    ("test.editor", "test.editor@example.com", "editor"),
    ("test.viewer", "test.viewer@example.com", "viewer"),
]

OUTSIDER = ("test.outsider", "test.outsider@example.com", "admin")
OUTSIDER_TENANT_NAME = "QA Isolation Tenant"
OUTSIDER_DEPARTMENT_NAME = "QA Isolation Dept"


def ensure_tenant_and_department(session: Session, tenant_name: str, dept_name: str):
    """Get or create a tenant and one department inside it."""
    tenant = session.execute(
        select(Tenant).where(Tenant.name == tenant_name)
    ).scalar_one_or_none()
    if tenant is None:
        tenant = Tenant(name=tenant_name)
        session.add(tenant)
        session.flush()

    department = session.execute(
        select(Department).where(
            Department.tenant_id == tenant.id, Department.name == dept_name
        )
    ).scalar_one_or_none()
    if department is None:
        department = Department(tenant_id=tenant.id, name=dept_name)
        session.add(department)
        session.flush()

    return tenant.id, department.id


def upsert_user(
    session: Session, *, username: str, email: str, role: str,
    password: str, tenant_id: int, department_id: int,
) -> str:
    """Create the user if absent. Returns a one-word status for the report."""
    existing = session.execute(
        select(User).where((User.username == username) | (User.email == email))
    ).scalar_one_or_none()

    if existing is not None:
        return "exists"

    session.add(
        User(
            tenant_id=tenant_id,
            department_id=department_id,
            username=username,
            email=email,
            password=get_hashed_password(password=password),
            role=role,
            is_active=True,
        )
    )
    session.flush()
    return "created"


def delete_test_users(session: Session) -> tuple[int, list[str]]:
    """
    Remove only the accounts this script creates.

    A user who owns documents is skipped rather than deleted: `documents.owner_id`
    is NOT NULL with no cascade, so deleting them raises an IntegrityError — and
    even if it did not, taking their documents with them is not something a
    cleanup flag should do silently. Returns (removed, skipped usernames).
    """
    names = [u[0] for u in TEST_USERS] + [OUTSIDER[0]]
    users = session.execute(select(User).where(User.username.in_(names))).scalars().all()

    removed = 0
    skipped: list[str] = []
    for user in users:
        owns = session.execute(
            select(Document.id).where(Document.owner_id == user.id).limit(1)
        ).first()
        if owns:
            skipped.append(user.username)
            continue
        session.delete(user)
        removed += 1

    return removed, skipped


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--password", default=DEFAULT_PASSWORD,
                        help=f"password for every test account (default: {DEFAULT_PASSWORD})")
    parser.add_argument("--with-outsider", action="store_true",
                        help="also create a user in a second tenant, to test isolation")
    parser.add_argument("--delete", action="store_true",
                        help="remove the test accounts instead of creating them")
    args = parser.parse_args()

    if len(args.password) < 5:
        print("Password must be at least 5 characters (the signup schema requires it).")
        return 2

    engine = create_engine(settings.sync_database_url)

    with Session(engine) as session:
        if args.delete:
            removed, skipped = delete_test_users(session)
            session.commit()
            print(f"Removed {removed} test account(s).")
            if skipped:
                print(
                    "Kept (they own documents — reassign or delete those first): "
                    + ", ".join(skipped)
                )
            engine.dispose()
            return 0

        rows = []
        for username, email, role in TEST_USERS:
            status = upsert_user(
                session, username=username, email=email, role=role,
                password=args.password,
                tenant_id=HOME_TENANT, department_id=HOME_DEPARTMENT,
            )
            rows.append((username, role, f"{HOME_TENANT}/{HOME_DEPARTMENT}", status))

        if args.with_outsider:
            tenant_id, department_id = ensure_tenant_and_department(
                session, OUTSIDER_TENANT_NAME, OUTSIDER_DEPARTMENT_NAME
            )
            username, email, role = OUTSIDER
            status = upsert_user(
                session, username=username, email=email, role=role,
                password=args.password,
                tenant_id=tenant_id, department_id=department_id,
            )
            rows.append((username, role, f"{tenant_id}/{department_id}", status))

        session.commit()

    engine.dispose()

    width = max(len(r[0]) for r in rows)
    print(f"\n{'username'.ljust(width)}  {'role':<7}  {'tenant/dept':<11}  status")
    print("-" * (width + 34))
    for username, role, scope, status in rows:
        print(f"{username.ljust(width)}  {role:<7}  {scope:<11}  {status}")

    print(f"\nPassword for all of the above: {args.password}")
    print("Log in at /login with the USERNAME (not the email) — the login route "
          "looks users up by username.")
    print("\nRemove them again with: python app/scripts/create_test_users.py --delete")
    print(
        "\n!! These are test accounts with a shared, known password. Do not create "
        "them on a deployment reachable from the internet, and delete them when "
        "you are done."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
