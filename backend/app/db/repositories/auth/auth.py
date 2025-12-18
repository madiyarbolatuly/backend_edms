from typing import Any, Coroutine, Tuple, List
from secrets import token_urlsafe

from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import or_

from app.api.dependencies.auth_utils import (
    create_access_token,
    create_refresh_token,
    get_hashed_password,
    verify_password,
)
from app.core.exceptions import http_400, http_403, http_404
from app.db.tables.auth.auth import User
from app.db.tables.documents.documents import Document
from app.db.tables.documents.shared import SharedDocument
from app.db.tables.documents.permissions import Permission
from app.db.tables.documents.notify import Notify
from app.schemas.auth.bands import (
    AdminCreateUser,
    AdminResetPassword,
    AdminUpdateUser,
    TokenData,
    UserAuth,
    UserOut,
)


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

    async def admin_list_users(
        self,
        *,
        tenant_id: int,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> Tuple[List[User], int]:
        base_stmt = select(User).where(User.tenant_id == tenant_id)
        if search:
            like_pattern = f"%{search.lower()}%"
            base_stmt = base_stmt.where(
                or_(
                    func.lower(User.username).like(like_pattern),
                    func.lower(User.email).like(like_pattern),
                )
            )

        total_stmt = select(func.count()).select_from(base_stmt.subquery())
        total_result = await self.session.execute(total_stmt)
        total = int(total_result.scalar_one())

        items_stmt = (
            base_stmt.order_by(User.created_at.desc()).offset(offset).limit(limit)
        )
        items_result = await self.session.execute(items_stmt)
        return items_result.scalars().all(), total

    async def admin_create_user(
        self, *, admin_ctx: TokenData, payload: AdminCreateUser
    ) -> tuple[UserOut, str]:
        """Create a new user on behalf of an admin and return temporary password."""
        tenant_id = admin_ctx.tenant_id
        department_id = payload.department_id or admin_ctx.department_id
        if department_id is None:
            raise http_400(msg="Department is required")

        raw_password = payload.password or token_urlsafe(8)

        user_payload = UserAuth(
            tenant_id=tenant_id,
            department_id=department_id,
            username=payload.username,
            email=payload.email,
            password=raw_password,
            role=payload.role,
        )

        user = await self.signup(user_payload)
        return user, raw_password

    async def _get_admin_scoped_user(self, tenant_id: int, user_id: str) -> User:
        stmt = select(User).where(User.id == user_id, User.tenant_id == tenant_id)
        result = await self.session.execute(stmt)
        user = result.scalar_one_or_none()
        if user is None:
            raise http_404(msg="User not found")
        return user

    async def admin_update_user(
        self,
        *,
        admin_ctx: TokenData,
        user_id: str,
        payload: AdminUpdateUser,
    ) -> UserOut:
        if (
            payload.role is None
            and payload.department_id is None
            and payload.is_active is None
        ):
            raise http_400(msg="No updates supplied")

        user = await self._get_admin_scoped_user(
            tenant_id=admin_ctx.tenant_id, user_id=user_id
        )

        updated = False

        if payload.role is not None and payload.role != user.role:
            user.role = payload.role
            updated = True

        if payload.department_id is not None:
            if payload.department_id <= 0:
                raise http_400(msg="Department id should be positive")
            if payload.department_id != user.department_id:
                user.department_id = payload.department_id
                updated = True

        if payload.is_active is not None and payload.is_active != user.is_active:
            user.is_active = payload.is_active
            updated = True

        if not updated:
            return user

        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def admin_reset_password(
        self,
        *,
        admin_ctx: TokenData,
        user_id: str,
        payload: AdminResetPassword,
    ) -> tuple[UserOut, str]:
        user = await self._get_admin_scoped_user(
            tenant_id=admin_ctx.tenant_id, user_id=user_id
        )

        raw_password = payload.password or token_urlsafe(8)
        user.password = get_hashed_password(raw_password)

        await self.session.commit()
        await self.session.refresh(user)

        return user, raw_password

    async def admin_delete_user(
        self,
        *,
        admin_ctx: TokenData,
        user_id: str,
    ) -> None:
        """Hard delete a user row from `users`.

        NOTE: Because many tables reference `users.id`, we must delete dependent rows first.
        This method removes:
        - shared_documents rows where user is shared_by/shared_with
        - permissions rows for the user
        - notify rows for the user
        - documents owned by the user (cascading delete for folder children is configured on Document)
        Then deletes the user.
        """
        # Prevent an admin from deleting themselves.
        if str(user_id) == str(admin_ctx.id):
            raise http_400(msg="Admin cannot delete themselves")

        user = await self._get_admin_scoped_user(
            tenant_id=admin_ctx.tenant_id, user_id=user_id
        )

        # 1) Delete deps that reference users.id
        await self.session.execute(
            delete(SharedDocument).where(
                or_(SharedDocument.shared_by == user_id, SharedDocument.shared_with == user_id)
            )
        )
        await self.session.execute(delete(Permission).where(Permission.user_id == user_id))
        await self.session.execute(delete(Notify).where(Notify.user_id == user_id))

        # 2) Delete documents owned by this user within this tenant.
        #    Document has a self-referential cascade for children.
        await self.session.execute(
            delete(Document).where(
                Document.owner_id == user_id,
                Document.tenant_id == admin_ctx.tenant_id,
            )
        )

        # 3) Finally delete the user.
        await self.session.delete(user)
        await self.session.commit()
