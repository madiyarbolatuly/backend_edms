from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from ..utils.session import get_db
from ..schemas.users import UserCreate
from ..utils.auth_utils import (
    get_password_hash,
    verify_access_token,
    verify_password,
    oauth2_scheme,
)
from ..models.users import Users
from . import create_permit_user


class UserService:

    @staticmethod
    async def create_user(db: Session, user: UserCreate, tenant_id: UUID) -> Users:
        """Static method to create a new user in the database."""
        hashed_password = get_password_hash(user.password)
        new_user = Users(
            email=user.email,
            password_hash=hashed_password,
            active_workspace=tenant_id,
            workspaces=[tenant_id],
            role=user.role,
        )
        new_user.add(new_user, db)
        new_user.save(db)

        await create_permit_user(
            str(new_user.id), str(new_user.active_workspace), user.role.value
        )
        return new_user

    @staticmethod
    def get_user_by_id(db: Session, id: UUID, tenant_id: UUID) -> Users:
        user = Users.get_by_id(db, id, tenant_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found."
            )
        return user

    @staticmethod
    def get_user_by_email(db: Session, email: str) -> Users:
        """Fetch a user by email."""
        return Users.get_one_by(db, email=email)

    @staticmethod
    def authenticate_user(db: Session, email: str, password: str) -> Users:
        """Authenticate a user by email and password."""
        user = UserService.get_user_by_email(db, email)
        if not user or not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def get_current_user(token: str, db: Session):
        credentials_exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
        username = verify_access_token(token, credentials_exception)
        user = UserService.get_user_by_email(db, username)
        if user is None:
            raise credentials_exception
        return user

    @staticmethod
    def update_user_password(
        db: Session, password: str, id: UUID, tenant_id: UUID
    ) -> Users:
        hashed_password = get_password_hash(password)
        user = UserService.get_user_by_id(db, id, tenant_id)
        user.update(db, password_hash=hashed_password)
        return user


# Wrapper for dependency injection
def get_current_user_dep(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
):

    return UserService.get_current_user(token, db)
