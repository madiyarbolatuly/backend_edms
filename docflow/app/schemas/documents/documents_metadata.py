from typing import Optional, List
from uuid import UUID

from app.schemas.documents.bands import DocumentMetadataBase


class DocumentMetadataCreate(DocumentMetadataBase):
    owner_id: Optional[str] = None
    name: str
    file_path: Optional[str] = None
    access_to: Optional[List[str]] = None


class DocumentMetadataRead(DocumentMetadataBase):
    id: UUID
    name: str
    file_path: Optional[str] = None


    class Config:
        from_attributes = True
