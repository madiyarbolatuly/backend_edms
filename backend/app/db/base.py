from sqlalchemy.ext.asyncio import AsyncSession
from typing import Generic, TypeVar
from sqlalchemy.orm import declarative_base

Base = declarative_base()

__all__ = ["Base"]  
ModelT = TypeVar("ModelT")

class BaseRepository(Generic[ModelT]):
    """Минимальный базовый репозиторий: хранит сессию."""
    def __init__(self, session: AsyncSession):
        self.session: AsyncSession = session
