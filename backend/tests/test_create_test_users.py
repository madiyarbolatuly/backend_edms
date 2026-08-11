"""
The manual-testing account seeder.

Exercised against a real (SQLite) database rather than mocks, because the point
of the script is that it inserts rows a person can then log in with — a mocked
session would prove nothing about the columns or the constraints.
"""
import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.api.dependencies.auth_utils import verify_password
from app.db.base import Base
from app.db.tables.auth.auth import User
from app.db.tables.departments import Department
from app.db.tables.documents.documents import Document
from app.db.tables.tenants import Tenant
from app.scripts.create_test_users import (
    HOME_DEPARTMENT,
    HOME_TENANT,
    TEST_USERS,
    delete_test_users,
    ensure_tenant_and_department,
    upsert_user,
)

PASSWORD = "Test1234!"


@pytest.fixture
def db(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'seed.db'}")
    # `documents` is needed too: deleting a user touches the ownership
    # relationship, and the script checks it before removing anyone.
    Base.metadata.create_all(
        engine,
        tables=[
            Tenant.__table__, Department.__table__, User.__table__,
            Document.__table__,
        ],
    )
    with Session(engine) as session:
        # The tenant/department the real data lives in.
        session.add(Tenant(id=HOME_TENANT, name="GQ Group"))
        session.add(
            Department(id=HOME_DEPARTMENT, tenant_id=HOME_TENANT, name="GQ Contract")
        )
        session.commit()
        yield session
    engine.dispose()


def seed(db, password=PASSWORD):
    results = [
        upsert_user(
            db, username=u, email=e, role=r, password=password,
            tenant_id=HOME_TENANT, department_id=HOME_DEPARTMENT,
        )
        for u, e, r in TEST_USERS
    ]
    db.commit()
    return results


def test_it_creates_one_user_per_role(db):
    assert seed(db) == ["created", "created", "created"]

    roles = db.execute(select(User.role)).scalars().all()
    assert {getattr(r, "value", r) for r in roles} == {"admin", "editor", "viewer"}


def test_the_password_actually_verifies(db):
    """The whole point — these have to be able to log in."""
    seed(db)

    user = db.execute(
        select(User).where(User.username == "test.admin")
    ).scalar_one()

    assert user.password != PASSWORD, "stored in the clear"
    assert verify_password(password=PASSWORD, hashed_password=user.password)


def test_users_land_in_the_tenant_that_holds_the_data(db):
    seed(db)

    for user in db.execute(select(User)).scalars():
        assert user.tenant_id == HOME_TENANT
        assert user.department_id == HOME_DEPARTMENT


def test_accounts_are_active(db):
    seed(db)

    assert all(u.is_active for u in db.execute(select(User)).scalars())


def test_running_it_twice_changes_nothing(db):
    seed(db)
    second = seed(db)

    assert second == ["exists", "exists", "exists"]
    assert db.execute(select(User)).scalars().all().__len__() == len(TEST_USERS)


def test_an_existing_username_is_never_overwritten(db):
    seed(db)
    before = db.execute(
        select(User).where(User.username == "test.admin")
    ).scalar_one().password

    seed(db, password="Совсем-другой-пароль")

    after = db.execute(
        select(User).where(User.username == "test.admin")
    ).scalar_one().password
    assert after == before


def test_the_outsider_gets_a_tenant_of_their_own(db):
    tenant_id, department_id = ensure_tenant_and_department(db, "QA Tenant", "QA Dept")
    db.commit()

    assert tenant_id != HOME_TENANT
    # A tenant with no department of its own could not hold a user at all.
    assert (
        db.execute(select(Department).where(Department.id == department_id))
        .scalar_one()
        .tenant_id
        == tenant_id
    )


def test_ensuring_the_same_tenant_twice_does_not_duplicate_it(db):
    first = ensure_tenant_and_department(db, "QA Tenant", "QA Dept")
    second = ensure_tenant_and_department(db, "QA Tenant", "QA Dept")
    db.commit()

    assert first == second
    assert len(db.execute(select(Tenant)).scalars().all()) == 2  # home + QA


def test_delete_removes_only_the_test_accounts(db):
    seed(db)
    db.add(
        User(
            id="real-user", tenant_id=HOME_TENANT, department_id=HOME_DEPARTMENT,
            username="real.person", email="real@example.com",
            password="x", role="editor",
        )
    )
    db.commit()

    removed, skipped = delete_test_users(db)
    db.commit()

    assert removed == len(TEST_USERS)
    assert skipped == []
    remaining = db.execute(select(User.username)).scalars().all()
    assert remaining == ["real.person"]


def test_a_test_user_who_owns_documents_is_kept(db):
    """
    `documents.owner_id` is NOT NULL with no cascade, so deleting such a user
    raises — and taking their documents with them is not something a `--delete`
    flag should do quietly.
    """
    seed(db)
    owner = db.execute(select(User).where(User.username == "test.editor")).scalar_one()
    db.add(
        Document(
            id=1, tenant_id=HOME_TENANT, department_id=HOME_DEPARTMENT,
            owner_id=owner.id, file_type="file", document_number="DOC-1",
            title="смета", name="смета.xlsx", status="public",
            file_path="смета.xlsx",
        )
    )
    db.commit()

    removed, skipped = delete_test_users(db)
    db.commit()

    assert skipped == ["test.editor"]
    assert removed == len(TEST_USERS) - 1
    assert (
        db.execute(select(User).where(User.username == "test.editor")).scalar_one_or_none()
        is not None
    )
