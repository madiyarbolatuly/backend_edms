from typing import Optional, List
from fastapi import UploadFile
from pydantic import BaseModel, ConfigDict
from datetime import datetime
from uuid import UUID

from ..models import UserRoles
from ..schemas.auth_token import AuthToken


class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str
    role: UserRoles
    workspace_id: Optional[str]


class UserProfileUpdate(BaseModel):
    name: Optional[str]
    avatar: Optional[UploadFile]


class UserSchema(UserBase):
    id: UUID
    workspaces: List[UUID]
    active_workspace: UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    role: str
    name: Optional[str] = None

    def model_dump(self, **kwargs):
        data = super().model_dump(**kwargs)
        # Convert UUID fields to strings
        data["id"] = str(data["id"])
        data["workspaces"] = [str(workspace_id) for workspace_id in data["workspaces"]]
        data["active_workspace"] = str(data["active_workspace"])
        # Convert datetime fields
        data["created_at"] = data["created_at"].isoformat()
        data["updated_at"] = data["updated_at"].isoformat()
        return data

    model_config = ConfigDict(from_attributes=True)


class LoginSchema(BaseModel):
    tokens: AuthToken
    user: UserSchema


class RegisterSchema(BaseModel):
    user: UserSchema
    tokens: AuthToken

    # model_config = {
    #     "from_attributes": True,
    #     "json_encoders": {UUID: str, datetime: lambda v: v.isoformat()},
    # }
