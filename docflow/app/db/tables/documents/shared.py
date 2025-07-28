# shared.py   (replaces old share_url)
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from app.db.models import Base

class SharedDocument(Base):
    __tablename__ = "shared_documents"

    id           = Column(Integer, primary_key=True)
    document_id  = Column(Integer, ForeignKey("documents.id"), nullable=False)
    shared_by    = Column(String(26), ForeignKey("users.id"), nullable=False)
    shared_with  = Column(String(26), ForeignKey("users.id"), nullable=False)
    token        = Column(String, unique=True, nullable=False)
    filename     = Column(String, nullable=False)  # ← Добавь это
    created_at   = Column(DateTime(timezone=True),
                          default=datetime.now(timezone.utc),
                          nullable=False)
    expires_at   = Column(DateTime(timezone=True))
