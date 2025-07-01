import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import UUID

from fastapi import UploadFile
from starlette.responses import FileResponse

from app.api.dependencies.constants import SUPPORTED_FILE_TYPES
from app.api.dependencies.repositories import get_file_path
from app.core.config import settings
from app.core.exceptions import http_400, http_404
from app.db.repositories.documents.documents_metadata import DocumentMetadataRepository
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.notify import NotifyRepo
from app.schemas.auth.bands import TokenData
from ulid import ULID

logger = logging.getLogger(__name__)


class DocumentMetadataBase:
    pass


class DocumentMetadataCreate(DocumentMetadataBase):
    owner_id: Optional[str] = None
    name: str
    file_path: Optional[str] = None
    parent_id: Optional[UUID] = None
    type: str = "file"
    access_to: Optional[List[str]] = None


class DocumentRepository:
    """
    Repository for managing documents on the local filesystem.
    """

    def __init__(self):
        # Root folder where all uploads live
        self.upload_root = Path(settings.upload_dir)

    async def _calculate_file_hash(self, file: UploadFile) -> str:
        """
        Reset the file pointer, hash the contents, then rewind.
        """
        file.file.seek(0)
        data = file.file.read()
        file.file.seek(0)
        return hashlib.sha256(data).hexdigest()

    async def _upload_new_file(
        self,
        file: UploadFile,
        folder: Optional[str],
        contents: bytes,
        file_type: str,
        user: TokenData,
    ) -> Dict[str, Any]:
        # Build user-specific subfolder path
        rel_folder = Path(user.id) / folder if folder else Path(user.id)
        abs_folder = self.upload_root / rel_folder
        abs_folder.mkdir(parents=True, exist_ok=True)

        # Generate a unique on-disk filename
        extension = SUPPORTED_FILE_TYPES[file_type]
        disk_filename = f"{ULID()}.{extension}"
        abs_path = abs_folder / disk_filename

        # Write the bytes to disk
        abs_path.write_bytes(contents)
        logger.info("Saved new file to %s", abs_path)

        rel_path = str(rel_folder / disk_filename)
        return {
            "response": "file_added",
            "upload": {
                "owner_id": user.id,
                "name": file.filename,
                "file_path": rel_path,
                "size": len(contents),
                "file_type": file_type,
                "file_hash": await self._calculate_file_hash(file),
            },
        }

    async def _upload_new_version(
        self,
        doc: Dict[str, Any],
        file: UploadFile,
        contents: bytes,
        file_type: str,
        new_file_hash: str,
        is_owner: bool,
    ) -> Dict[str, Any]:
        # Overwrite the existing file on disk
        rel_path = Path(doc["file_path"])
        abs_path = self.upload_root / rel_path
        abs_path.write_bytes(contents)
        logger.info("Overwrote existing file at %s", abs_path)

        return {
            "response": "file_updated",
            "is_owner": is_owner,
            "upload": {
                "name": file.filename,
                "file_path": str(rel_path),
                "size": len(contents),
                "file_type": file_type,
                "file_hash": new_file_hash,
            },
        }

    async def upload(
        self,
        metadata_repo: DocumentMetadataRepository,
        user_repo: AuthRepository,
        file: UploadFile,
        folder: Optional[str],
        user: TokenData,
    ) -> Dict[str, Any]:
        """
        Uploads a new file or updates an existing one based on content hash.
        """
        file_type = file.content_type
        if file_type not in SUPPORTED_FILE_TYPES:
            logger.warning("Unsupported file type: %s", file_type)
            raise http_400(msg=f"File type {file_type} not supported.")

        contents = await file.read()
        new_hash = await self._calculate_file_hash(file)

        try:
            existing = (await metadata_repo.get(document=file.filename, owner=user)).__dict__
            if existing.get("file_hash") != new_hash:
                # content changed → new version
                return await self._upload_new_version(
                    doc=existing,
                    file=file,
                    contents=contents,
                    file_type=file_type,
                    new_file_hash=new_hash,
                    is_owner=True,
                )
            # no change detected
            logger.info("Upload skipped: no content change for %s", file.filename)
            return {
                "response": "File already present and no changes detected.",
                "upload": None,
            }

        except Exception:
            # not found → brand-new upload
            logger.info("Uploading new file %s for user %s", file.filename, user.id)
            return await self._upload_new_file(
                file=file,
                folder=folder,
                contents=contents,
                file_type=file_type,
                user=user,
            )

    async def download(self, name: str) -> FileResponse:
        """
        Returns a FileResponse to stream the named file.
        """
        try:
            path = await get_file_path(name)
        except FileNotFoundError as e:
            logger.error("Download failed, file not found: %s", name)
            raise http_404(msg=str(e)) from e

        return FileResponse(path, filename=name)

    async def preview(self, document: Dict[str, Any]) -> FileResponse:
        """
        Streams the file inline for browser preview if supported.
        """
        name = document.get("name")
        try:
            path = await get_file_path(name)
        except FileNotFoundError as e:
            logger.error("Preview failed, file not found: %s", name)
            raise http_404(msg=str(e)) from e

        ext = Path(name).suffix.lower()
        if ext in {".jpg", ".jpeg", ".png", ".gif"}:
            media_type = f"image/{ext.lstrip('.')}"
        elif ext == ".pdf":
            media_type = "application/pdf"
        else:
            logger.warning("Unsupported preview type: %s", ext)
            raise http_404(msg="Unsupported file type for preview.")

        return FileResponse(path, media_type=media_type)
