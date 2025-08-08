from typing import Optional, List
from uuid import UUID
from app.schemas.base import BaseSchema
from pydantic import Field
from datetime import datetime


from app.schemas.documents.bands import DocumentMetadataBase, DocStatus


class DocumentMetadataCreate(DocumentMetadataBase):
    tenant_id: int
    department_id: int
    owner_id: Optional[str] = None
    name: str
    file_path: Optional[str] = None
    parent_id: Optional[int] = None
    type: str = "file"
    is_archived: bool = False
    is_favourited: bool = False

class DocumentMetadataRead(DocumentMetadataBase):
    id: int
    name: str
    file_path: Optional[str] = None
    size: Optional[str] = None
    tags: Optional[List[str]] = []
    status: DocStatus

class FolderCreate(BaseSchema):
    name: str = Field(..., description="Folder name")
    parent_id: Optional[int] = Field(None, description="Parent folder ID")

class FolderRead(BaseSchema):
    id: UUID
    owner_id: str
    name: str
    type: str
    parent_id: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True
        orm_mode = True
        arbitrary_types_allowed = True