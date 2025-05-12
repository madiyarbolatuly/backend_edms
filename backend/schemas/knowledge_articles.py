from pydantic import BaseModel, ConfigDict
from uuid import UUID
from typing import Optional, List
from datetime import datetime

from ..models import ArticleStatus


class ArticleCreateSchema(BaseModel):
    title: str
    tenant_id: str
    author_id: str
    content: str
    tags: Optional[List[str]] = None


class ArticleUpdateSchema(BaseModel):
    title: Optional[str] = None
    content: Optional[str] = None
    tags: Optional[List[str]] = None

    model_config = ConfigDict(from_attributes=True)


class ArticleSchema(BaseModel):
    id: UUID
    title: str
    tenant_id: UUID
    author_id: UUID
    content: str
    status: ArticleStatus
    created_at: datetime
    updated_at: datetime
    tags: Optional[List[str]]

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert UUID fields to strings
        data["id"] = str(data["id"])
        data["author_id"] = str(data["author_id"])
        data["tenant_id"] = str(data["tenant_id"])
        data["status"] = data["status"].value
        # Convert datetime fields
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        return data

    model_config = ConfigDict(from_attributes=True)
