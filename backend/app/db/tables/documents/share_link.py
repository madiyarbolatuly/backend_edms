from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db.base import Base


class ShareLink(Base):
    """
    A public, tokenised link to one document or folder.

    Deliberately separate from `shared_documents`:
      * that table requires a registered recipient (`shared_with` is NOT NULL)
        and mints a token per document, so a folder produced dozens of tokens;
      * a share link is a single token for the whole object, usable by anyone
        who has the URL — no account needed.

    Access scope is derived from the target at request time (the target itself
    plus everything beneath it), so it stays correct as the folder changes.
    """

    __tablename__ = "share_links"

    id          = Column(Integer, primary_key=True)
    token       = Column(String(64), nullable=False, unique=True, index=True)

    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    document    = relationship("Document")

    created_by  = Column(String(255), ForeignKey("users.id"), nullable=False)
    created_at  = Column(DateTime(timezone=True), nullable=False,
                         default=lambda: datetime.now(timezone.utc))

    # NULL = no expiry
    expires_at  = Column(DateTime(timezone=True), nullable=True)
    # Set instead of deleting, so a revoked link reports "revoked" rather than 404
    revoked_at  = Column(DateTime(timezone=True), nullable=True)
