"""
Shared test fixtures.

The app reads its Postgres settings at import time (`app/core/config.py` calls
`int(os.environ.get("POSTGRES_PORT"))` while the module is being loaded), so the
environment has to be in place before anything under `app.` is imported. That is
why the env setup below runs at module scope, above the app imports.

Tests run against SQLite rather than the deployment's Postgres so that `pytest`
works with no services running. Everything exercised here — recursive CTEs,
`lower()` ordering, `ILIKE`, `OFFSET/LIMIT` — behaves the same on both. The one
Postgres-only thing in the schema, the `text_pattern_ops` index, is a dialect
kwarg SQLAlchemy simply skips on SQLite.
"""
import os
from pathlib import Path

import pytest
import pytest_asyncio
from dotenv import load_dotenv

BACKEND_ROOT = Path(__file__).resolve().parents[1]

# `load_dotenv()` searches upward from the working directory and so misses
# app/.env when pytest is run from the backend root. Point it at the file.
load_dotenv(BACKEND_ROOT / "app" / ".env")

# Defaults for anything the .env does not carry, so a checkout without one
# still collects. These are never connected to — the tests use SQLite.
os.environ.setdefault("POSTGRES_USER", "test")
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("DATABASE_HOSTNAME", "localhost")
os.environ.setdefault("POSTGRES_PORT", "5432")
os.environ.setdefault("POSTGRES_DB", "test")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret")
os.environ.setdefault("JWT_REFRESH_SECRET_KEY", "test-refresh-secret")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MIN", "30")
os.environ.setdefault("REFRESH_TOKEN_EXPIRE_MIN", "1440")

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine  # noqa: E402

from app.db.base import Base  # noqa: E402
from app.db.tables.base_class import DocStatus  # noqa: E402
from app.db.tables.documents.documents import Document  # noqa: E402
from app.db.repositories.documents.documents_metadata import MetadataRepository  # noqa: E402
from app.schemas.auth.bands import TokenData  # noqa: E402

TENANT_ID = 1
DEPARTMENT_ID = 1
OWNER_ID = "user-1"


@pytest.fixture
def owner() -> TokenData:
    """The caller every repository method is scoped to."""
    return TokenData(
        id=OWNER_ID,
        username="tester",
        tenant_id=TENANT_ID,
        department_id=DEPARTMENT_ID,
    )


@pytest_asyncio.fixture
async def session():
    """A session over a fresh in-memory database, one per test."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        # `documents`, plus `users`: every listing resolves owner labels through
        # `_owner_labels`, which selects from `users`. Creating documents alone
        # made each of those calls fail with "no such table: users". The rows
        # themselves are not needed — the lookup simply finds nothing — and
        # SQLite does not enforce the FKs, so no user rows are inserted.
        from app.db.tables.auth.auth import User

        await conn.run_sync(
            Base.metadata.create_all, tables=[Document.__table__, User.__table__]
        )

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def repo(session) -> MetadataRepository:
    return MetadataRepository(session)


@pytest_asyncio.fixture
async def full_session():
    """
    A session over the documents table *and* everything that references it.

    Needed by the permanent-delete tests, which clear dependent rows before
    removing a document. Kept separate from `session` so the rest of the suite
    does not pay for the extra tables.

    `Notify` is deliberately excluded: its `postgresql.UUID` and
    `postgresql.ENUM` columns do not compile on SQLite.
    """
    from app.db.tables.auth.auth import User
    from app.db.tables.departments import Department
    from app.db.tables.documents.permissions import Permission
    from app.db.tables.documents.share_link import ShareLink
    from app.db.tables.documents.shared import SharedDocument
    from app.db.tables.documents.versions import DocumentVersion
    from app.db.tables.tenants import Tenant

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    # NB: `doc_user_access` is an alias for `Permission.__table__`, not a second
    # table — listing both would try to create `permissions` twice.
    tables = [
        Tenant.__table__, Department.__table__, User.__table__, Document.__table__,
        Permission.__table__, SharedDocument.__table__,
        ShareLink.__table__, DocumentVersion.__table__,
    ]

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all, tables=tables)

    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with maker() as s:
        yield s

    await engine.dispose()


@pytest_asyncio.fixture
async def full_repo(full_session) -> MetadataRepository:
    return MetadataRepository(full_session)


@pytest.fixture
def make_full_document(full_session):
    """`make_document`, against the `full_session` database."""
    counter = {"n": 0}

    async def _make(
        name: str,
        *,
        parent_id: int | None = None,
        file_type: str = "file",
        status: DocStatus = DocStatus.public,
        deleted_at=None,
        owner_id: str = OWNER_ID,
        doc_id: int | None = None,
    ) -> Document:
        counter["n"] += 1
        n = counter["n"]
        doc = Document(
            id=doc_id if doc_id is not None else n,
            tenant_id=TENANT_ID,
            department_id=DEPARTMENT_ID,
            owner_id=owner_id,
            file_type=file_type,
            document_number=f"DOC-{n:05d}",
            title=f"{name}-{n}",
            name=name,
            status=status,
            file_path=f"{name}-{n}",
            size=1,
            parent_id=parent_id,
            deleted_at=deleted_at,
        )
        full_session.add(doc)
        await full_session.flush()
        return doc

    return _make


@pytest.fixture
def make_document(session):
    """
    Insert a document row.

    Defaults are chosen so a caller only has to say what the test is about —
    a name, a parent, maybe a size.
    """
    counter = {"n": 0}

    async def _make(
        name: str,
        *,
        parent_id: int | None = None,
        file_type: str = "file",
        size: int | None = 1,
        status: DocStatus = DocStatus.public,
        tenant_id: int = TENANT_ID,
        department_id: int = DEPARTMENT_ID,
        owner_id: str = OWNER_ID,
        doc_id: int | None = None,
        created_at=None,
        # Storage-relative path. Defaulted so the tests written before this
        # parameter existed are unaffected; the folder-size and move tests set
        # it explicitly because the path *is* what they are about.
        file_path: str | None = None,
    ) -> Document:
        counter["n"] += 1
        n = counter["n"]
        doc = Document(
            id=doc_id if doc_id is not None else n,
            tenant_id=tenant_id,
            department_id=department_id,
            owner_id=owner_id,
            file_type=file_type,
            document_number=f"DOC-{n:05d}",
            title=f"{name}-{n}",
            name=name,
            status=status,
            file_path=file_path if file_path is not None else f"/files/{n}/{name}",
            size=size,
            parent_id=parent_id,
        )
        if created_at is not None:
            doc.created_at = created_at
        session.add(doc)
        await session.flush()
        return doc

    return _make


@pytest.fixture
def colleague() -> TokenData:
    """A second caller inside the *same* tenant and department."""
    return TokenData(
        id="user-2",
        username="colleague",
        tenant_id=TENANT_ID,
        department_id=DEPARTMENT_ID,
    )


@pytest.fixture
def other_owner() -> TokenData:
    """A caller from a different tenant, for the scoping tests."""
    return TokenData(
        id="user-999",
        username="outsider",
        tenant_id=999,
        department_id=999,
    )


@pytest.fixture
def uploads(tmp_path, monkeypatch):
    """
    Point `settings.upload_dir` at a temporary directory.

    `upload_dir` is a property over `local_storage_path`, and the code under
    test reads `settings.upload_dir` at call time, so patching the underlying
    attribute works.

    Caveat: `app/api/dependencies/repositories.py` binds `UPLOAD_DIR` at *import*
    time, so `get_file_path` does not follow this patch. Do not write a test
    that assumes it does.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "local_storage_path", str(tmp_path))
    return tmp_path
