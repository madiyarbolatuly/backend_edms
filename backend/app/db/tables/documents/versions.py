from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from app.db.models import Base


class DocumentVersion(Base):
    __tablename__ = "document_versions"

    id              = Column(Integer, primary_key=True)
    document_id     = Column(Integer, ForeignKey("documents.id"), nullable=False)
    version_number  = Column(Integer, nullable=False)
    file_path       = Column(String, nullable=False)
    created_at      = Column(DateTime(timezone=True),
                             default=lambda: datetime.now(timezone.utc),
                             nullable=False)

    __table_args__  = (UniqueConstraint("document_id", "version_number",
                                        name="uq_doc_version"),)
