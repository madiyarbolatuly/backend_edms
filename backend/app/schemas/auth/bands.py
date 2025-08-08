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