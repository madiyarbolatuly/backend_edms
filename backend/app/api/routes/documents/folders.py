from fastapi import APIRouter, Depends, status, HTTPException
from typing import Optional
from uuid import UUID

from app.api.dependencies.auth_utils import get_current_user, TokenData
from app.api.dependencies.repositories import get_repository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.schemas.documents.documents_metadata import FolderCreate, DocumentMetadataRead

router = APIRouter(prefix="/folders", tags=["Folders"])

@router.post("/", response_model=DocumentMetadataRead, status_code=status.HTTP_201_CREATED)
async def create_folder(
    data: FolderCreate,
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    if data.parent_id:
        parent = await repo.get(document=data.parent_id, owner=user)
        if not parent or getattr(parent, "file_type", getattr(parent, "type", None)) != "folder":
            raise HTTPException(status_code=400, detail="Parent must be a folder.")
            
    folder = await repo.create_folder(
        owner_id=user.id,
        tenant_id=user.tenant_id,
        department_id=user.department_id,
        data=data
    )
    # Через repo, а не напрямую: response_model сериализует ORM-объект без
    # owner_name/owner_email, и новая папка приходила бы без имени владельца.
    return await repo.serialize_one(folder)

@router.get(
    "/{parent_id}/children",
    response_model=list[DocumentMetadataRead],
    summary="List items in a folder",
)
async def list_folder_children(
    # `Document.id` is an Integer and the frontend calls this with a number, so
    # the UUID annotation made every real request a 422.
    parent_id: int,
    recursive: bool = False,
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    return await repo.list_children(user=user, parent_id=parent_id, recursive=recursive)
