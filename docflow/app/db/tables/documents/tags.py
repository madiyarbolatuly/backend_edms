from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, UniqueConstraint
from app.db.base import Base


class Tag(Base):
    __tablename__ = "tags"
    id          = Column(Integer, primary_key=True)
    name        = Column(String, nullable=False, unique=True)
    created_at  = Column(DateTime(timezone=True),
                         default=datetime.now(timezone.utc),
                         nullable=False)


class DocumentTag(Base):
    __tablename__ = "document_tags"
    id          = Column(Integer, primary_key=True)
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    tag_id      = Column(Integer, ForeignKey("tags.id"), nullable=False)

    __table_args__ = (UniqueConstraint("document_id", "tag_id",
                                       name="uq_doc_tag"),)
