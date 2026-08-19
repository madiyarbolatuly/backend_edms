from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, Boolean, DateTime,
    Enum as SQLEnum, ForeignKey
)
from sqlalchemy.orm import relationship
from app.db.base import Base
from enum import Enum as PyEnum      # import the *real* Enum

from app.core.utils import get_ulid
class UserRole(str, PyEnum):
    admin  = "admin"
    editor = "editor"
    viewer = "viewer"


class User(Base):
    __tablename__ = "users"

    id             = Column(String(255), primary_key=True, default=get_ulid, unique=True)
    tenant_id      = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    department_id  = Column(Integer, ForeignKey("departments.id"), nullable=False)

    username       = Column(String, unique=True, nullable=False)
    email          = Column(String, unique=True, nullable=False)
    password       = Column(String, nullable=False)      # store **hash**
    role           = Column(SQLEnum(UserRole), nullable=False, default=UserRole.viewer)

    is_active      = Column(Boolean, default=True, nullable=False)
    created_at     = Column(DateTime(timezone=True),
                            nullable=False,
                            default=lambda: datetime.now(timezone.utc))

    documents      = relationship("Document", back_populates="owner",
                                  foreign_keys="Document.owner_id")

