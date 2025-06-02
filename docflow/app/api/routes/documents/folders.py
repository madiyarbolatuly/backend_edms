from fastapi import APIRouter, Depends, status
from typing import List, Optional
from uuid import UUID

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository
from app.db.repositories.documents.documents_metadata import DocumentMetadataRepository
from app.schemas.documents.documents_metadata import FolderCreate, FolderRead

router = APIRouter(tags=["Folders"], prefix="/folders")

@router.post(
    "",
    response_model=FolderRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new folder",
)
async def create_folder(
    data: FolderCreate,
    current_user=Depends(get_current_user),
    repo: DocumentMetadataRepository = Depends(get_repository(DocumentMetadataRepository))
):
    """
    Create a folder under an optional parent folder.
    """
    return await repo.create_folder(owner_id=current_user.id, data=data)

@router.get(
    "/{parent_id}/children",
    response_model=List[FolderRead],
    summary="List items in a folder",
)
async def list_folder_children(
    parent_id: UUID,
    current_user=Depends(get_current_user),
    repo: DocumentMetadataRepository = Depends(get_repository(DocumentMetadataRepository)),
):
    """
    List folders and files inside the specified folder.
    """
    return await repo.list_children(owner_id=current_user.id, parent_id=parent_id)
