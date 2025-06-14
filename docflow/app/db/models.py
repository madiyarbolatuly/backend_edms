import logging

from sqlalchemy import create_engine, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from app.core.config import settings
from app.core.exceptions import http_500

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

Base = declarative_base()
metadata = Base.metadata


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

    # Update the document list query to exclude archived documents
    from app.db.tables.documents.documents_metadata import DocumentMetadata

    stmt = select(DocumentMetadata).where(DocumentMetadata.is_archived == False)
