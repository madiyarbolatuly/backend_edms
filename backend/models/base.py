from sqlalchemy import Column, func, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from uuid import uuid4
from typing import Any, List, Optional, Type, TypeVar
from sqlalchemy.orm import Session

Base = declarative_base()

T = TypeVar("T", bound="BaseModel")


class BaseModel(Base):
    __abstract__ = True

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(
        DateTime, default=func.now(), onupdate=func.now(), nullable=False
    )

    def add(self, obj: Any, session: Session) -> None:
        """Adds the obj to the current db session."""
        if obj is not None:
            try:
                session.add(obj)
            except Exception as ex:
                session.rollback()
                raise ex

    def save(self, session: Session) -> None:
        """Commits all changes of the current db session."""
        try:
            session.commit()
            session.refresh(self)
        except Exception as ex:
            session.rollback()
            raise ex

    def delete(self, session: Session) -> None:
        """Deletes the current object from the database."""
        try:
            session.delete(self)
            session.commit()
        except Exception as ex:
            session.rollback()
            raise ex

    @classmethod
    def get_by_id(
        cls: Type[T], session: Session, obj_id: Any, tenant_id: Optional[Any] = None
    ) -> Optional[T]:
        """Retrieve an object by its primary key and optional tenant_id."""
        query = session.query(cls).filter_by(id=obj_id)

        # Apply tenant_id filter only if it's provided and the model has 'tenant_id'
        if tenant_id and hasattr(cls, "tenant_id"):
            query = query.filter_by(tenant_id=tenant_id)

        return query.first()

    @classmethod
    def get_all(cls: Type[T], session: Session) -> List[T]:
        """Retrieve all objects of this type."""
        return session.query(cls).all()

    @classmethod
    def filter_by(cls: Type[T], session: Session, **filters) -> List[T]:
        """Filter objects by given conditions."""
        return session.query(cls).filter_by(**filters).all()

    @classmethod
    def get_one_by(cls: Type[T], session: Session, **filters) -> List[T]:
        """Filter objects by given conditions."""
        return session.query(cls).filter_by(**filters).first()

    @classmethod
    def delete_by_id(cls: Type[T], session: Session, obj_id: Any) -> None:
        """Delete an object by its primary key."""
        obj = cls.get_by_id(session, obj_id)
        if obj:
            try:
                session.delete(obj)
                session.commit()
            except Exception as ex:
                session.rollback()
                raise ex

    def update(self, **kwargs) -> None:
        """Update fields of the current object."""
        for key, value in kwargs.items():
            setattr(self, key, value)
