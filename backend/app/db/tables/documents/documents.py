from datetime import datetime, timezone
from ulid import ULID
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey,
    Enum as SQLEnum, UniqueConstraint
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship, Mapped
from enum import Enum as PyEnum
from app.db.base import Base
from app.db.tables.base_class import DocStatus




class Document(Base):
    __tablename__ = "documents"

    id              = Column(Integer, primary_key=True)
    tenant_id       = Column(Integer, ForeignKey("tenants.id"), nullable=False)
    department_id   = Column(Integer, ForeignKey("departments.id"), nullable=False)

    owner_id        = Column(String(255), ForeignKey("users.id"), nullable=False)
    owner           = relationship("User", back_populates="documents")
    file_type        = Column(String(255), nullable=False, server_default="file")
    document_number = Column(String, nullable=False, unique=True, default=lambda: str(ULID()))
    title           = Column(String, nullable=False)
    name           = Column(String, nullable=False, unique=True)  # file name
    status          = Column(SQLEnum(DocStatus), nullable=False, default=DocStatus.draft)
    file_path       = Column(String, nullable=False)     # local FS path
    is_archived     = Column(Boolean, default=False, nullable=False)
    is_favourited   = Column(Boolean, default=False, nullable=False)
    file_hash       = Column(String, nullable=True)
    created_at      = Column(DateTime(timezone=True),
                             default=datetime.now(timezone.utc),
                             nullable=False)
    deleted_at      = Column(DateTime(timezone=True))    # set when moved to trash

    # folders (optional – keep if you need a tree)
    parent_id: Mapped[int | None] = Column(Integer, ForeignKey("documents.id"))
    
    children        = relationship("Document", backref="parent",
                                   cascade="all, delete",
                                   remote_side="Document.id")

    __table_args__  = (UniqueConstraint("title", "parent_id",
                                        name="uq_title_parent"),)
