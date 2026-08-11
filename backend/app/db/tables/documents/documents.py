from datetime import datetime, timezone
from ulid import ULID
from sqlalchemy import (
    Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey,
    Enum as SQLEnum, Index, UniqueConstraint, func, text
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
    # NOTE: intentionally NOT globally unique — the same file name legitimately
    # appears in different folders. Uniqueness within a folder is enforced by
    # uq_title_parent; uniqueness of a physical path by uniq_file (below).
    name           = Column(String, nullable=False)  # file name
    status          = Column(SQLEnum(DocStatus), nullable=False, default=DocStatus.draft)
    file_path       = Column(String, nullable=False)     # local FS path
    is_archived     = Column(Boolean, default=False, nullable=False)
    is_favourited   = Column(Boolean, default=False, nullable=False)
    file_hash       = Column(String, nullable=True)
    # Bytes on disk. NULL for folders — their size is aggregated on read.
    size            = Column(BigInteger, nullable=True)
    # The default must be a callable. `default=datetime.now(timezone.utc)` is
    # evaluated once, while this module is being imported, so every row inserted
    # without an explicit value was stamped with the *process start time* —
    # which made `sort_by=created_at` meaningless. Same fix applied across every
    # table module; `share_link.py` already had it right.
    created_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc),
                             nullable=False)
    deleted_at      = Column(DateTime(timezone=True))    # set when moved to trash

    # folders (optional – keep if you need a tree)
    parent_id: Mapped[int | None] = Column(Integer, ForeignKey("documents.id"))
    
    children        = relationship("Document", backref="parent",
                                   cascade="all, delete",
                                   remote_side="Document.id")

    __table_args__  = (
        UniqueConstraint("title", "parent_id", name="uq_title_parent"),
        # One row per physical path within a tenant/department. The filesystem
        # importer (app/scan/scan_and_upload.py) upserts against this.
        UniqueConstraint("tenant_id", "department_id", "file_path",
                         name="uniq_file"),

        # Every listing — folder contents, the tree, the recursive CTE walk —
        # filters on tenant + department + status and then on parent_id. Without
        # these the planner seq-scans the whole table for one folder's children,
        # which is the difference between a snappy tree and a multi-second one on
        # a library of tens of thousands of rows.
        Index("ix_documents_parent_id", parent_id),
        Index("ix_documents_scope", tenant_id, department_id, status),
        # Matches the ORDER BY of a folder listing (folders first, then name),
        # so a page can be read straight off the index.
        Index("ix_documents_parent_type_name", parent_id, file_type,
              func.lower(name)),
        # `_folder_sizes` aggregates children with `file_path LIKE 'parent/%'`.
        # A btree only serves a prefix LIKE under text_pattern_ops.
        Index("ix_documents_file_path_prefix", file_path,
              postgresql_ops={"file_path": "text_pattern_ops"}),
    )
