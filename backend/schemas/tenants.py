from pydantic import BaseModel
from typing import Optional
from uuid import UUID
from datetime import datetime


class TenantCreateSchema(BaseModel):
    name: str
    description: Optional[str]
    owner: Optional[UUID]


class TenantUpdateSchema(BaseModel):
    name: Optional[str]
    description: Optional[str]


class TenantSchema(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    owner: Optional[UUID]
    created_at: datetime
    updated_at: datetime
