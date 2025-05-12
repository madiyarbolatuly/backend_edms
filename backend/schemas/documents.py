from pydantic_settings import BaseModel
from typing import Optional
from enum import Enum

class DocumentUploadResponse(BaseModel):
    document_id: int
    version_id: int
    message: str

class DocumentStatus(str, Enum):
    draft = "draft"
    review = "review"
    published = "published"
    archived = "archived"
