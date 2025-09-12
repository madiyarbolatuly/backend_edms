from fileinput import filename
import os
from typing import List, Optional, Union
from uuid import UUID
from pathlib import Path
from fastapi.responses import FileResponse
from sqlalchemy.engine import Row
from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository, get_file_path
from app.core.exceptions import http_400, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.documents import DocumentRepository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.schemas.auth.bands import TokenData
from app.schemas.documents.documents_metadata import DocumentMetadataRead
from app.schemas.documents.document_sharing import SharingRequest
from fastapi import (
    APIRouter, Depends, File, HTTPException, UploadFile, status
)
from app.db.tables.documents.documents import Document
from pathlib import PurePosixPath

from fastapi.responses import FileResponse
from app.db.models import logger


router = APIRouter(tags=["Document"])
# routes/documents.py
@router.get("/file/{file_id:int}/download")
async def download_by_id(
    file_id: int,
    repo: DocumentRepository = Depends(get_repository(DocumentRepository)),
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
):
    return await repo.download(file_id, metadata_repository, user)

@router.get(
    "/trash",
    status_code=status.HTTP_200_OK,
    name="list_of_bin",
)
async def list_bin(
    metadata_repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
):
    return await metadata_repository.bin_list(owner=user)

@router.delete(
    "/trash",
    status_code=status.HTTP_204_NO_CONTENT,
    name="empty_trash",
)
async def empty_trash(
    metadata_repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    await metadata_repository.empty_bin(owner=user)

@router.delete(
    "/trash/{file_name:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="permanently_delete_doc",
)
async def perm_delete(
    file_name: str,
    metadata_repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    trash = await metadata_repository.bin_list(owner=user)
    for entry in trash.get("response", []):
        if entry.name == file_name:
            await metadata_repository.perm_delete_a_doc(document=entry.id, owner=user)
            return
    raise http_404(msg=f"No file with name '{file_name}' in trash.")

@router.post(
    "/restore/{file}",
    status_code=status.HTTP_200_OK,
    response_model=DocumentMetadataRead,
    name="restore_from_bin",
)
async def restore_bin(
    file: str,
    metadata_repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> DocumentMetadataRead:
    return await metadata_repository.restore(file=file, owner=user)

@router.delete(
    "/{file_name:path}",
    status_code=status.HTTP_204_NO_CONTENT,
    name="add_to_bin"
)
async def add_to_bin(
    file_name: str,
    metadata_repository: MetadataRepository = Depends(
        get_repository(MetadataRepository)
    ),
    user: TokenData = Depends(get_current_user),
) -> None:
    await metadata_repository.delete(document=file_name, owner=user)

@router.get(
    "/preview/{document}",
    status_code=status.HTTP_200_OK,
    name="preview_document",
)
async def get_document_preview(
    document: Union[str, UUID],
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
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

@router.post("/upload-folder-bulk", status_code=status.HTTP_200_OK)
async def upload_folder_bulk(
    files: List[UploadFile] = File(...),
    parent_id: Optional[int] = None,  # read from query string automatically
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    """
    Safe bulk upload of nested files/folders.

    - Preserves subfolder structure from UploadFile.filename (relativePath/webkitRelativePath).
    - If `parent_id` provided, anchors the entire uploaded tree under that folder.
    """

    if not files:
        raise HTTPException(status_code=400, detail="No files were provided.")

    # 1) Collect all unique nested folder paths (POSIX)
    folder_paths: set[str] = set()
    for f in files:
        rel = PurePosixPath(f.filename)

        # basic safety
        if rel.is_absolute() or ".." in rel.parts:
            raise HTTPException(status_code=400, detail=f"Invalid path: {f.filename}")

        parts = rel.parts[:-1]
        accum = []
        for part in parts:
            accum.append(part)
            folder_paths.add("/".join(accum))

    # 2) Create/get folders and build path→id map (anchored to parent_id)
    try:
        folder_map: dict[str, int] = {}
        if folder_paths:
            folder_map = await repo.bulk_create_folders(
                list(folder_paths),
                tenant_id=user.tenant_id,
                user_id=user.id,
                department_id=user.department_id,
                base_parent_id=parent_id,
            )
    except Exception as e:
        try:
            await repo.session.rollback()
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Ошибка при создании папок: {e}")

    results: list = []
    try:
        for file in files:
            rel = PurePosixPath(file.filename)
            parent_posix = rel.parent.as_posix()
            folder_norm = "" if parent_posix == "." else parent_posix
            filename = rel.name

            result = await repo.upload_with_streaming(
                file=file,
                folder=folder_norm or None,
                filename=filename,
                user=user,
                parent_map=folder_map,
                base_parent_id=parent_id,  # <<— don’t forget this
            )
            results.append(result)

        try:
            await repo.session.commit()
        except Exception:
            pass

    except Exception as e:
        if hasattr(e, "file_path") and getattr(e, "file_path"):
            Path(getattr(e, "file_path")).unlink(missing_ok=True)
        try:
            await repo.session.rollback()
        except Exception:
            pass
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка при загрузке {getattr(file, 'filename', '')}: {e}",
        )

    return {"uploaded": len(results), "results": results}

@router.post(
    "/upload",
    status_code=status.HTTP_201_CREATED,
    name="upload_documents"
)
async def upload_documents(
    files: List[UploadFile] = File(...),
    folder: Optional[str] = None,
    preserve_structure: bool = False,
    parent_id: Optional[int] = None,
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository))
):
    """
    Upload files with optional folder structure preservation
    """
    if preserve_structure:
        return await upload_folder_bulk(files,parent_id, user, repo)
    else:
        # Handle single folder upload (existing logic)
        results = []
        for file in files:
            # Normalize single folder input to POSIX (if provided)
            folder_norm = None if folder is None else PurePosixPath(folder).as_posix()
            filename = PurePosixPath(file.filename).name

            result = await repo.upload_with_streaming(
                file=file,
                folder=folder_norm,
                filename=filename,
                user=user,
                parent_id=parent_id,
                base_parent_id=parent_id
            )
            results.append(result)
        return {"uploaded": len(results), "results": results}

@router.get("/children/{parent_id}")
async def list_children(
    parent_id: Optional[int] = None,
    repo: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
):
    return await repo.list_children(owner_id=user.id, parent_id=parent_id)
