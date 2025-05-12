from typing import Dict, List, Optional, Union
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, status, File, UploadFile, Depends
from fastapi.responses import FileResponse
from sqlalchemy.engine import Row

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository, get_file_path
from app.core.exceptions import http_400, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.documents import DocumentRepository
from app.db.repositories.documents.documents_metadata import DocumentMetadataRepository
from app.schemas.auth.bands import TokenData
from app.schemas.documents.documents_metadata import DocumentMetadataRead

router = APIRouter(tags=["Document"])

@router.post(
    "/upload",
    response_model=List[DocumentMetadataRead],
    status_code=status.HTTP_201_CREATED,
    name="upload_document",
)
async def upload(
    files: List[UploadFile] = File(...),
    folder: Optional[str] = None,
    repository: DocumentRepository = Depends(DocumentRepository),
    metadata_repository: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user_repository: AuthRepository = Depends(get_repository(AuthRepository)),
    user: TokenData = Depends(get_current_user),
) -> List[DocumentMetadataRead]:
    if not files:
        raise http_400(msg="No input files provided.")
    responses = []
    for file in files:
        res = await repository.upload(
            metadata_repo=metadata_repository,
            user_repo=user_repository,
            file=file,
            folder=folder,
            user=user,
        )
        if res["response"] == "file_added":
            responses.append(
                await metadata_repository.upload(document_upload=res["upload"])
            )
        elif res["response"] == "file_updated":
            responses.append(
                await metadata_repository.patch(
                    document=res["upload"]["name"],
                    document_patch=res["upload"],
                    owner=user,
                    user_repo=user_repository,
                    is_owner=res.get("is_owner", False),
                )
            )
    return responses

@router.get(
    "/file/{file_name}/download",
    status_code=status.HTTP_200_OK,
    name="download_document",
)
async def download(
    file_name: str,
    repository: DocumentRepository = Depends(DocumentRepository),
    metadata_repository: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> FileResponse:
    if not file_name:
        raise http_400(msg="No file name provided.")
    try:
        metadata = await metadata_repository.get(document=file_name, owner=user)
    except Exception:
        raise http_404(msg=f"No file with name '{file_name}' found.")
    meta = dict(metadata)
    try:
        path = await get_file_path(meta["file_path"])
    except FileNotFoundError as e:
        raise http_404(msg=str(e))
    return FileResponse(path, filename=meta["name"])

@router.delete(
    "/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="add_to_bin"
)
async def add_to_bin(
    file_name: str,
    metadata_repository: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    await metadata_repository.delete(document=file_name, owner=user)

@router.get(
    "/trash",
    status_code=status.HTTP_200_OK,
    response_model=None,
    name="list_of_bin",
)
async def list_bin():
    return await metadata_repo.bin_list(owner=owner)

@router.delete(
    "/trash/{file_name}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="permanently_delete_doc",
)
async def perm_delete(
    file_name: Optional[str] = None,
    delete_all: bool = False,
    metadata_repository: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    try:
        trash = await metadata_repository.bin_list(owner=user)
        if delete_all:
            await metadata_repository.empty_bin(owner=user)
        elif trash.get("response"):
            for entry in trash["response"]:
                if entry.DocumentMetadata.name == file_name:
                    await metadata_repository.perm_delete_a_doc(
                        document=entry.DocumentMetadata.id,
                        owner=user
                    )
                    break
        else:
            raise http_404(msg=f"No file with name '{file_name}' in trash.")
    except Exception:
        raise http_404(msg=f"No file with name '{file_name}'")

@router.post(
    "/restore/{file}",
    status_code=status.HTTP_200_OK,
    response_model=DocumentMetadataRead,
    name="restore_from_bin",
)
async def restore_bin(
    file: str,
    metadata_repo: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> DocumentMetadataRead:
    return await metadata_repo.restore(file=file, owner=user)

@router.delete(
    "/trash",
    status_code=status.HTTP_204_NO_CONTENT,
    name="empty_trash",
)
async def empty_trash(
    metadata_repo: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    await metadata_repo.empty_bin(owner=user)

@router.get(
    "/preview/{document}",
    status_code=status.HTTP_200_OK,
    name="preview_document",
)
async def get_document_preview(
    document: Union[str, UUID],
    repository: DocumentRepository = Depends(DocumentRepository),
    metadata_repository: DocumentMetadataRepository = Depends(
        get_repository(DocumentMetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> FileResponse:
    if not document:
        raise http_404(msg="Enter document id or name.")
    try:
        metadata = await metadata_repository.get(document=document, owner=user)
    except Exception:
        raise http_404(msg="Document does not exist.")
    meta = dict(metadata)
    try:
        path = await get_file_path(meta["file_path"])
    except FileNotFoundError as e:
        raise http_404(msg=str(e))
    ext = Path(meta["name"]).suffix.lower()
    if ext in {".jpg", ".jpeg", ".png", ".gif"}:
        media_type = f"image/{ext.lstrip('.')}"
    elif ext == ".pdf":
        media_type = "application/pdf"
    else:
        raise http_400(msg="File type is not supported for preview")
    return FileResponse(path, media_type=media_type, filename=meta["name"])
