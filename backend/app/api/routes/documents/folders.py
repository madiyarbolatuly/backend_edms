from fastapi import APIRouter, Depends, status, HTTPException
from typing import Optional
from uuid import UUID

from app.api.dependencies.auth_utils import get_current_user, TokenData
from app.api.dependencies.repositories import get_repository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.schemas.documents.documents_metadata import FolderCreate, DocumentMetadataRead

router = APIRouter(prefix="/folders", tags=["Folders"])

@router.post(
    "/",  # ← use "/" to avoid trailing-slash ambiguity
    response_model=DocumentMetadataRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new folder",
)
async def create_folder(
    data: FolderCreate,
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    # (optional) validate parent exists & is a folder
    if data.parent_id:
        parent = await repo.get(document=data.parent_id, owner=user)
        if not parent or getattr(parent, "file_type", getattr(parent, "type", None)) != "folder":
            raise HTTPException(status_code=400, detail="Parent must be a folder.")
    return await repo.create_folder(owner_id=user.id, data=data)

@router.get(
    "/{parent_id}/children",
    response_model=list[DocumentMetadataRead],
    summary="List items in a folder",
)
async def list_folder_children(
    parent_id: UUID,
    recursive: bool = False,
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    return await repo.list_children(owner_id=user.id, parent_id=parent_id, recursive=recursive)
