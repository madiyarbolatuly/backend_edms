from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import Depends
from app.db.tables.auth.auth import User
from app.core.exceptions import http_404


async def get_user_by_id(
        session: AsyncSession,
        user_id: str,
        
        ):
    """
    Retrieve a user by their ID.

    Args:
        session (AsyncSession): The database session.
        user_id (str): The ID of the user to retrieve.

    Returns:
        User: The user object if found.

    Raises:
        HTTP_404: If the user is not found.
    """
    stmt = select(User).where(User.id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise http_404(msg=f"User with ID {user_id} not found.")

    return (await session.execute(stmt)).scalar_one()

