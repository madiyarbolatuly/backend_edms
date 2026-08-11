import logging
from sqlalchemy import create_engine, inspect, select
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.schema import CreateIndex
from app.db.base import Base
from app.core.config import settings
from app.core.exceptions import http_500
from app.db.tables.auth.auth import User                     # noqa: F401
from app.db.tables.documents.documents import Document  # noqa: F401
from app.db.tables.documents.documents import Document  # noqa: F401
from app.db.tables.departments import Department
from app.db.tables.documents.documents import Document
from app.db.tables.documents.share_link import ShareLink        # noqa: F401

logger = logging.getLogger("sqlalchemy")

engine = create_engine(
    url=settings.sync_database_url,
    echo=settings.db_echo_log,
)

async_engine = create_async_engine(
    url=settings.async_database_url,
    echo=settings.db_echo_log,
    query_cache_size=0,
)

session = sessionmaker(bind=engine, autocommit=False, autoflush=False)

async_session = sessionmaker(
    bind=async_engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)

metadata = Base.metadata


def ensure_indexes() -> None:
    """
    Create any index declared on a model that the live table is missing.

    `metadata.create_all` only builds indexes as part of creating a table, so a
    database that already has `documents` never picks up an index added to the
    model afterwards. These are exactly the indexes the folder listings depend
    on, and without them every query for one folder's children seq-scans the
    whole library — so they are reconciled explicitly on boot rather than left
    to whoever remembers to run DDL by hand.

    Failing here must not stop the app: a missing index is slow, not broken.
    """
    inspector = inspect(engine)
    for table in metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {ix["name"] for ix in inspector.get_indexes(table.name)}
        for index in table.indexes:
            if index.name in existing:
                continue
            try:
                with engine.begin() as conn:
                    conn.execute(CreateIndex(index))
                logger.info("Created missing index %s on %s", index.name, table.name)
            except SQLAlchemyError as e:
                # Losing a race with another worker booting at the same time is
                # the expected failure here, and it means the index now exists.
                logger.warning("Could not create index %s: %s", index.name, e)


async def check_tables():
    try:
        with Session(engine) as _session:
            # Create tables
            metadata.create_all(engine)
            _session.commit()
            logger.info("Tables created if they didn't already exist.")
    except OperationalError as e:
        logger.error("Error Creating table: %s", e)
        raise http_500(msg="An error occurred while creating tables.") from e

    ensure_indexes()

    # Update the document list query to exclude archived documents

    stmt = select(Document).where(Document.is_archived == False)
