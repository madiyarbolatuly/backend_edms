from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi.security import OAuth2PasswordBearer
from jose import jwt, JWTError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import http_401
from app.schemas.auth.bands import TokenData
from fastapi import Depends, HTTPException, status


# Password Hashing
password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
# oauth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v2/u/login", scheme_name="JWT")


def get_hashed_password(password: str) -> str:
    return password_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_context.verify(password, hashed_password)


def create_access_token(
    subject: Dict[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(
            minutes=settings.access_token_expire_min
        )

    to_encode = {
        "exp": expires_delta,
        "id": subject.get("id"),
        "username": subject.get("username"),
        "role": subject.get("role"),
        "tenant_id": subject.get("tenant_id"),
        "department_id": subject.get("department_id"),
    }

    return jwt.encode(to_encode, settings.jwt_secret_key, settings.algorithm)


def create_refresh_token(
    subject: Dict[str, Any], expires_delta: timedelta = None
) -> str:
    if expires_delta is not None:
        expires_delta = datetime.utcnow() + expires_delta
    else:
        expires_delta = datetime.utcnow() + timedelta(
            minutes=settings.refresh_token_expire_min
        )

    to_encode = {
        "exp": expires_delta,
        "id": subject.get("id"),
        "username": subject.get("username"),
        "role": subject.get("role"),
        "tenant_id": subject.get("tenant_id"),
        "department_id": subject.get("department_id"),
    }

    return jwt.encode(to_encode, settings.jwt_secret_key, settings.algorithm)


def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.algorithm]
        )
        uid = payload.get("id")
        username = payload.get("username")
        role = payload.get("role")
        tenant_id = payload.get("tenant_id")
        department_id = payload.get("department_id")
        if username is None:
            raise credentials_exception
        token_data = TokenData(
            id=uid, 
            username=username,
            role=role, 
            tenant_id=tenant_id, 
            department_id=department_id)
    except JWTError as e:
        raise credentials_exception from e

    return token_data


def get_current_user(token: str = Depends(oauth2_scheme)) -> TokenData:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.algorithm])
        user_data = TokenData(**payload)
    except JWTError:
        raise credentials_exception
    if not user_data.id:
        raise credentials_exception
    return user_data


def get_current_admin(user: TokenData = Depends(get_current_user)) -> TokenData:
    """Ensure the currently authenticated user is an admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return user


#: Roles allowed to decide on a document under review. Viewers are read-only,
#: so approving is limited to the two roles that can already change documents.
REVIEWER_ROLES = frozenset({"admin", "editor"})


def get_current_reviewer(user: TokenData = Depends(get_current_user)) -> TokenData:
    """Ensure the caller may approve or reject a document."""
    if user.role not in REVIEWER_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Требуются права редактора или администратора",
        )
    return user
