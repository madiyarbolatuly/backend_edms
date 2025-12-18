from fastapi import APIRouter, Depends, Query, status

from app.api.dependencies.auth_utils import get_current_admin
from app.api.dependencies.repositories import get_repository
from app.db.repositories.auth.auth import AuthRepository
from app.schemas.auth.bands import (
    AdminCreateUser,
    AdminCreateUserResponse,
    AdminResetPassword,
    AdminResetPasswordResponse,
    AdminUpdateUser,
    AdminUserListResponse,
    TokenData,
    UserOut,
)

router = APIRouter(prefix="/users", tags=["Admin :: Users"])


@router.get("", response_model=AdminUserListResponse)
async def list_users(
    *,
    admin: TokenData = Depends(get_current_admin),
    repository: AuthRepository = Depends(get_repository(AuthRepository)),
    search: str | None = Query(default=None, max_length=128),
    limit: int = Query(default=25, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    items, total = await repository.admin_list_users(
        tenant_id=admin.tenant_id,
        search=search.strip() if search else None,
        limit=limit,
        offset=offset,
    )
    return {"items": items, "total": total}


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=AdminCreateUserResponse,
)
async def create_user(
    *,
    admin: TokenData = Depends(get_current_admin),
    repository: AuthRepository = Depends(get_repository(AuthRepository)),
    payload: AdminCreateUser,
):
    user, password = await repository.admin_create_user(
        admin_ctx=admin,
        payload=payload,
    )
    return {"user": user, "temporary_password": password}


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(
    *,
    user_id: str,
    admin: TokenData = Depends(get_current_admin),
    repository: AuthRepository = Depends(get_repository(AuthRepository)),
    payload: AdminUpdateUser,
):
    return await repository.admin_update_user(
        admin_ctx=admin,
        user_id=user_id,
        payload=payload,
    )


@router.post(
    "/{user_id}/reset-password",
    response_model=AdminResetPasswordResponse,
)
async def reset_password(
    *,
    user_id: str,
    admin: TokenData = Depends(get_current_admin),
    repository: AuthRepository = Depends(get_repository(AuthRepository)),
    payload: AdminResetPassword | None = None,
):
    payload = payload or AdminResetPassword()
    user, password = await repository.admin_reset_password(
        admin_ctx=admin,
        user_id=user_id,
        payload=payload,
    )
    return {"user": user, "temporary_password": password}


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    *,
    user_id: str,
    admin: TokenData = Depends(get_current_admin),
    repository: AuthRepository = Depends(get_repository(AuthRepository)),
) -> None:
    await repository.admin_delete_user(admin_ctx=admin, user_id=user_id)
    return None
