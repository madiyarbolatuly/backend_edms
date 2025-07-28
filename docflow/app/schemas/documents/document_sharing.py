from typing import List, Optional
from datetime import datetime
from app.schemas.base import BaseSchema

from app.schemas.documents.bands import DocumentSharingBase


class DocumentSharingCreate(DocumentSharingBase): ...


class DocumentSharingRead(DocumentSharingBase):
    url_id: str
    visits: int

    class Config:
        from_attributes = True


class SharingRequest(BaseSchema):
    visits: int = 1 
    share_to: Optional[List[str]] = None  # emails, or usernames of users to share.
    expires_at: Optional[datetime] = None