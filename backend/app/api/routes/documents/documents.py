from fileinput import filename
import os
from typing import List, Optional, Union
from uuid import UUID
from pathlib import Path

from fastapi import APIRouter, status, File, UploadFile, Depends, HTTPException
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
from fastapi import UploadFile
from app.db.tables.documents.documents import Document
from pathlib import PurePosixPath

from app.db.models import logger


router = APIRouter(tags=["Document"])

@router.get(
    "/file/{file_name}/download",
    status_code=status.HTTP_200_OK,
    name="download_document",
)
async def download(
    file_name: str,
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
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

@router.post("/upload-folder-bulk")
async def upload_folder_bulk(
    files: List[UploadFile] = File(...),
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository))
):
    """
    Безопасная массовая загрузка вложенных файлов и папок с транзакцией
    """

    # 1) Собираем все уникальные вложенные пути (POSIX)
    folder_paths: set[str] = set()
    for f in files:
        rel = PurePosixPath(f.filename)
        parts = rel.parts[:-1]
        for i in range(len(parts)):
            folder_paths.add("/".join(parts[: i + 1]))

    # 2) Создаём (или получаем) все папки в БД и строим карту путей → id
    folder_map: dict[str, int] = {}
    try:
        if folder_paths:
            folder_map = await repo.bulk_create_folders(
                list(folder_paths),
                tenant_id=user.tenant_id,
                user_id=user.id,
                department_id=user.department_id,
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при создании папок: {e}")

    # 3) Обрабатываем файлы стримингом
    results: list = []
    for file in files:
        try:
            rel = PurePosixPath(file.filename)
            parent_posix = rel.parent.as_posix()
            folder_norm = "" if parent_posix == "." else parent_posix

            filename = rel.name

            result = await repo.upload_with_streaming(
                file=file,
                folder=folder_norm,
                filename=filename,
                user=user,
                parent_map=folder_map,
            )
            results.append(result)
        except Exception as e:
            if hasattr(e, "file_path") and e.file_path:
                Path(e.file_path).unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Ошибка при загрузке {file.filename}: {e}")

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
    user: TokenData = Depends(get_current_user),
    repo: MetadataRepository = Depends(get_repository(MetadataRepository))
):
    """
    Upload files with optional folder structure preservation
    """
    if preserve_structure:
        return await upload_folder_bulk(files, user, repo)
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
                parent_map={},  # Empty map for single file upload
            )
            results.append(result)
        return {"uploaded": len(results), "results": results}

