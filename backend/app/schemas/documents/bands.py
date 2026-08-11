from datetime import datetime
from typing import Optional, List
from uuid import UUID

from app.schemas.base import BaseSchema
from app.db.tables.base_class import DocStatus, NotifyEnum


# Document Metadata
class DocumentMetadataBase(BaseSchema):
    id: UUID
    tenant_id: int                
    department_id: int             
    owner_id: str
    name: str
    file_path: str
    created_at: datetime
    deleted_at: Optional[datetime] = None   #(trash)
    size: Optional[int]
    file_type: Optional[str]
    is_archived: bool = False     
    is_favourited: bool = False    #(renamed from starred)
    tags: Optional[List[str]]
    status: DocStatus
    parent_id: Optional[int] = None

    class Config:
        from_attributes = True


class DocumentMetadataPatch(BaseSchema):
    name: str = None
    tags: Optional[List[str]] = None
    categories: Optional[List[str]] = None
    access_to: Optional[List[str]] = None


# Document Sharing
class DocumentSharingBase(BaseSchema):
    url_id: str
    owner_id: str
    name: str
    url: str
    expires_at: datetime
    visits: int
    share_to: Optional[List[str]] = None


class DocUserAccess(BaseSchema):
    id: str
    doc_id: UUID
    user_id: str

    class Config:
        from_attribute = True


class DocUserAccessCreate(BaseSchema):
    doc_id: str
    user_id: str


# Notifications
class Notification(BaseSchema):
    # Field names follow the `notify` table. They used to be `receiver_id` and
    # `notified_at`, which are not columns — so validating a real row raised
    # ValidationError and `GET /v2/notifications` failed for any user who had
    # even one notification. It only appeared to work while the table was empty.
    id: UUID
    user_id: str
    message: str
    status: NotifyEnum
    created_at: datetime


class NotifyPatchStatus(BaseSchema):
    status: NotifyEnum = NotifyEnum.unread
    mark_all: bool = False
