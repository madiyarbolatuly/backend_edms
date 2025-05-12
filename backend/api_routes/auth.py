from datetime import datetime
import uuid
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.services.users import UserService
from ..services import TenantService
from ..utils.auth_utils import (
    create_access_token,
    create_refresh_token,
    verify_access_token,
    oauth2_scheme,
    blacklisted_tokens,
)
from ..schemas.users import LoginSchema, RegisterSchema, UserCreate, UserSchema
from ..schemas.auth_token import RefreshTokenResponse
from ..utils.session import get_db
from ..schemas import StandardResponse

authRouter = APIRouter(prefix="/auth", tags=["Auth"])


@authRouter.post("/register", response_model=StandardResponse[RegisterSchema])
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    """
    Endpoint to create a new user account if the email doesn't already exist
    """
    existing_user = UserService.get_user_by_email(db, user.email)

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User already exists.",
        )

    tenant_data = {
        "name": f"Default-{uuid.uuid4()}",
        "description": "Default organisation",
        "owner": None,
    }
    # create tenant
    new_tenant = await TenantService.create_tenant(db, tenant_data)

    # Create the new user
    new_user = await UserService.create_user(db, user, new_tenant.id)
    new_tenant.update(owner=new_user.id)
    new_tenant.save(db)

    access_token = create_access_token(data={"sub": user.email})
    refresh_token = create_refresh_token(data={"sub": user.email})

    user_schema = UserSchema.model_validate(new_user)

    return JSONResponse(
        {
            "data": {
                "user": user_schema.model_dump(),
                "tokens": {
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                },
            },
            "status": "success",
        },
        status_code=status.HTTP_201_CREATED,
    )




@authRouter.get("/refresh", response_model=StandardResponse[RefreshTokenResponse])
def refresh_token(refresh_token: str, db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "data": {},
            "message": "Could not validate credentials",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )
    email = verify_access_token(refresh_token, credentials_exception)
    new_access_token = create_access_token(data={"sub": email})

    return JSONResponse(
        content={
            "data": {"access_token": new_access_token},
            "message": "Token refreshed successfully",
            "status": "success",
        },
        status_code=status.HTTP_200_OK,
    )


@authRouter.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    response_model=StandardResponse[dict],
)
async def logout(token: str = Depends(oauth2_scheme)):
    """
    Revoke the token by blacklisting it.
    """
    blacklisted_tokens[token] = datetime.now()
    return JSONResponse(
        content={"data": None, "status": "success"}, status_code=status.HTTP_200_OK
    )
