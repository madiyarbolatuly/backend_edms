from typing import List, Optional
from datetime import datetime
from pydantic import BaseModel

from app.schemas.documents.bands import DocumentSharingBase


class DocumentSharingCreate(DocumentSharingBase): ...


class DocumentSharingRead(DocumentSharingBase):
    url_id: str
    visits: int

    class Config:
        from_attributes = True


class SharingRequest(BaseModel):
    visits: int = 1 
    share_to: Optional[List[str]] = None  # emails, or usernames of users to share.
    expires_at: Optional[datetime] = None