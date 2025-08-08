from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession
from app.db.models import async_session  # this is your async_sessionmaker

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields a scoped AsyncSession
    and guarantees proper close/rollback after the response.
    """
    async with async_session() as session:        # open session
        try:
            yield session                         # hand it to the endpoint/CRUD
            await session.flush()                # commit if all is well
        except:                                   # noqa: E722 - re-raise later
            await session.rollback()              # rollback on error
            raise
