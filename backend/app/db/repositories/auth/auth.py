from typing import Any, Coroutine

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_

from app.api.dependencies.auth_utils import (
    create_access_token,
    create_refresh_token,
    get_hashed_password,
    verify_password,
)
from app.core.exceptions import http_400, http_403
from app.db.tables.auth.auth import User
from app.schemas.auth.bands import UserAuth, UserOut


class AuthRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _check_user_or_none(
        self, userdata: UserAuth
    ) -> Coroutine[Any, Any, Any | None]:
        stmt = select(User).where(
        or_(User.username == userdata.username, User.email == userdata.email)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_user(self, field: str, detail: str):
        stmt = ""
        if field == "username":
            stmt = select(User).where(User.username == detail)
        elif field == "email":
            stmt = select(User).where(User.email == detail)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def signup(self, userdata: UserAuth) -> UserOut:
        # Checking if the user already exists
        if await self._check_user_or_none(userdata) is not None:
            raise http_400(msg="User with details already exists")

        # hashing the password
        hashed_password = get_hashed_password(password=userdata.password)
        userdata.password = hashed_password

        new_user = User(**userdata.model_dump(exclude_unset=True))

        self.session.add(new_user)
        await self.session.commit()
        await self.session.refresh(new_user)

        return new_user

    async def login(self, ipdata):
        user = await self.get_user(field="username", detail=ipdata.username)
        if user is None:
            raise http_403(msg="Recheck the credentials")
        user_dict = user.__dict__
        hashed_password = user_dict.get("password")
        if not verify_password(
            password=ipdata.password, hashed_password=hashed_password
        ):
            raise http_403("Incorrect Password")

        payload = {
            "id": user_dict.get("id"),
            "username": user_dict.get("username"),
            "role": user_dict.get("role"),
            "tenant_id": user_dict.get("tenant_id"),
            "department_id": user_dict.get("department_id"),
        }

        return {
            "token_type": "bearer",
            "access_token": create_access_token(
                subject=payload
            ),
            "refresh_token": create_refresh_token(
                subject=payload
            ),
            
        }

    async def get_user_by_id(self, user_id: str):
        stmt = select(User).where(User.id == user_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email_or_username(self, key: str):
        stmt = select(User).where(or_(User.email == key, User.username == key))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
