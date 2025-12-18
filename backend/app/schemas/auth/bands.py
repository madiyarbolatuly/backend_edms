from datetime import datetime
from typing import Annotated, Optional
from ulid import ULID
from app.schemas.base import BaseSchema 
from pydantic import EmailStr, Field
PydanticULID = Annotated[str, ULID]

# ----------------------------- INPUT SCHEMAS ----------------------------- #
class UserAuth(BaseSchema):
    """Credentials for sign-up / sign-in."""
    tenant_id:     int                # NEW  – ties user to tenant
    department_id: int                # NEW
    username:      str       = Field(..., min_length=3, max_length=50)
    email:         EmailStr  = Field(..., description="Email ID")
    password:      str       = Field(..., min_length=5, max_length=64)
    role:          str       = Field('viewer', description="admin/editor/viewer")


class AdminCreateUser(BaseSchema):
    username:      str       = Field(..., min_length=3, max_length=50)
    email:         EmailStr  = Field(...)
    role:          str       = Field('viewer')
    department_id: Optional[int] = None
    tenant_id:     Optional[int] = None
    password:      Optional[str] = Field(None, min_length=5, max_length=64)


class AdminUpdateUser(BaseSchema):
    role: Optional[str] = Field(default=None)
    department_id: Optional[int] = Field(default=None)
    is_active: Optional[bool] = Field(default=None)


class AdminResetPassword(BaseSchema):
    password: Optional[str] = Field(default=None, min_length=5, max_length=64)

# ----------------------------- OUTPUT SCHEMAS ---------------------------- #
class UserOut(BaseSchema):
    id:            PydanticULID
    tenant_id:     int
    department_id: int
    username:      str
    email:         EmailStr
    role:          str
    is_active:     bool                = True
    created_at:    datetime

    class Config:
        from_attributes = True

# ------------------------------ TOKEN SCHEMAS --------------------------- #
class Token(BaseSchema):
    access_token: str
    token_type:   str                 = "bearer"

class TokenData(BaseSchema):
    id:       Optional[str]  = None
    username: Optional[str]  = None
    role:     Optional[str]  = None
    tenant_id: int 
    department_id: int 


class AdminUserListResponse(BaseSchema):
    items: list[UserOut]
    total: int


class AdminCreateUserResponse(BaseSchema):
    user: UserOut
    temporary_password: str


class AdminResetPasswordResponse(BaseSchema):
    user: UserOut
    temporary_password: str