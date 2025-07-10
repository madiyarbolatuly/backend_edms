from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, Enum as SQLEnum, ForeignKey, String
from app.db.base import Base
from enum import Enum as PyEnum


class AccessLevel(str, PyEnum):
    read  = "read"
    write = "write"
    admin = "admin"


class Permission(Base):
    __tablename__ = "permissions"

    id           = Column(Integer, primary_key=True)
    document_id  = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id      = Column(String(26), ForeignKey("users.id"), nullable=False)
    access_level = Column(SQLEnum(AccessLevel), nullable=False)
    created_at   = Column(DateTime(timezone=True),
                          default=datetime.now(timezone.utc),
                          nullable=False)
