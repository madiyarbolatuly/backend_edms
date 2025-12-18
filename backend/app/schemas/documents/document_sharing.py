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


class SharedDocumentRead(BaseSchema):
    id: int
    token: str
    document_id: int
    filename: str
    file_path: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: datetime
    shared_by: str
    shared_by_name: Optional[str] = None
    shared_with: str
    shared_with_name: Optional[str] = None

    class Config:
        from_attributes = True


class SharedDocumentUpdate(BaseSchema):
    filename: Optional[str] = None
    expires_at: Optional[datetime] = None


class SharedDocumentListResponse(BaseSchema):
    items: List[SharedDocumentRead]