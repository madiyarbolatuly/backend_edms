from datetime import datetime, timezone
from uuid import uuid4

from typing import List, Optional
from sqlalchemy import (
    Column,
    String,
    Integer,
    ARRAY,
    text,
    DateTime,
    Enum,
    ForeignKey,
    Table,
    UniqueConstraint,
    Boolean,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.db.models import Base
from app.db.tables.base_class import StatusEnum


doc_user_access = Table(
    "doc_user_access",
    Base.metadata,
    Column(
        "doc_id",
        UUID(as_uuid=True),
        ForeignKey("document_metadata.id", ondelete="CASCADE"),
    ),
    Column("user_id", String(26), ForeignKey("users.id")),
    UniqueConstraint("doc_id", "user_id", name="uq_doc_user_access_doc_user"),
)


class DocumentMetadata(Base):
    __tablename__ = "document_metadata"

    id = Column(UUID(as_uuid=True), primary_key=True, index=True, nullable=False, default=uuid4, server_default=text("gen_random_uuid()"))
    owner_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    file_path: Optional[str] = Column(String, nullable=False)

    #--Folder creation

    type: Mapped[str] = Column(Enum("file", "folder", name="document_type"), 
                               nullable=False, default="file")
    parent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("document_metadata.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent: Mapped["DocumentMetadata"] = relationship(
        "DocumentMetadata",
        remote_side=[id],
        back_populates="children"
    )
    children: Mapped[List["DocumentMetadata"]] = relationship(
        "DocumentMetadata",
        back_populates="parent",
        cascade="all, delete"
    )

    __table_args__ = (
        UniqueConstraint("name", "parent_id", name="uq_name_parent"),  # no duplicate names in same folder
    )
    #--Folder creation

    created_at = Column(
        DateTime(timezone=True),
        default=datetime.now(timezone.utc),
        nullable=False,
        server_default=text("NOW()"),
    )
    size: Optional[int] = Column(Integer)
    file_type: Optional[str] = Column(String)
    tags: Optional[List[str]] = Column(ARRAY(String))
    categories: Optional[List[str]] = Column(ARRAY(String))
    status: Enum = Column(Enum(StatusEnum), default=StatusEnum.private)
    file_hash: Optional[str] = Column(String)
    access_to: Optional[List[str]] = Column(ARRAY(String))
    type = Column(String, default='file')  # 'file' or 'folder'
    parent_id = Column(UUID(as_uuid=True), ForeignKey('document_metadata.id'), nullable=True)
    owner = relationship("User", back_populates="owner_of")
    is_archived = Column(Boolean, nullable=False, default=False)
    is_starred = Column(Boolean, nullable=False, default=False)

    update_access = relationship(
        "User", secondary=doc_user_access, passive_deletes=True
    )
