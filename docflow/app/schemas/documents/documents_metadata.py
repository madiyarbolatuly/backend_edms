from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime


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

class FolderCreate(BaseModel):
    name: str = Field(..., description="Folder name")
    parent_id: Optional[UUID] = Field(None, description="Parent folder ID")

class FolderRead(BaseModel):
    id: UUID
    owner_id: str
    name: str
    type: str
    parent_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True
