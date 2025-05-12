from datetime import datetime, timedelta
from typing import Dict
from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
import jwt
from jwt.exceptions import PyJWTError

from .. import settings


# Context for password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
optional_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v2/u//login", auto_error=False)
blacklisted_tokens: Dict[str, datetime] = {}


# Function to hash password
def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str):
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate an access token that expires after a short duration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def create_refresh_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate a refresh token that expires after a longer duration"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (
        expires_delta or timedelta(days=settings.refresh_token_expire_days)
    )
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(
        to_encode, settings.secret_key, algorithm=settings.algorithm
    )
    return encoded_jwt


def verify_access_token(token: str, credentials_exception):
    """Verifies Access and Refresh tokens"""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
        return email
    except PyJWTError:
        raise credentials_exception


async def verify_token_blacklist(request: Request, call_next):
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    if token in blacklisted_tokens:
        return JSONResponse(
            status_code=401,
            content={"message": "Token is revoked.", "status": "fail", "data": {}},
        )

    response = await call_next(request)
    return response
