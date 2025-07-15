# app/db/tables/documents/permissions.py
from datetime import datetime, timezone
from enum import Enum as PyEnum

from sqlalchemy import (
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    String,
)
from app.db.models import Base


class AccessLevel(str, PyEnum):
    read = "read"
    write = "write"
    admin = "admin"


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    user_id = Column(String(26), ForeignKey("users.id"), nullable=False)
    access_level = Column(SQLEnum(AccessLevel), nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
    )


# --------------------------------------------------------------------------- #
# Alias the mapped table so existing `from …permissions import doc_user_access`
# statements keep working.
# --------------------------------------------------------------------------- #
doc_user_access = Permission.__table__     
__all__ = ("Permission", "doc_user_access") 
