import logging
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional, List
from uuid import UUID
from sqlalchemy import select, func
from fastapi import UploadFile
from starlette.responses import FileResponse
import zipfile
import tempfile            # ← fixes "tempfile is not defined"

from starlette.background import BackgroundTask   # ⟵ for cleanup after response

from app.api.dependencies.constants import SUPPORTED_FILE_TYPES
from app.api.dependencies.repositories import get_file_path
from app.core.config import settings
from app.core.exceptions import http_400, http_404
from app.db.repositories.documents.notify import NotifyRepo
from app.db.tables.documents.documents import Document, DocStatus
from app.db.tables.documents.versions import DocumentVersion
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.db.base import BaseRepository
from app.schemas.auth.bands import TokenData
from ulid import ULID
from sqlalchemy.ext.asyncio import AsyncSession
import shutil
logger = logging.getLogger(__name__)


class DocumentMetadataBase:
    name: str
    description: str | None = None 


class DocumentMetadataCreate(DocumentMetadataBase):
    owner_id: Optional[str] = None
    name: str
    file_path: Optional[str] = None
    parent_id: Optional[int] = None
    type: str = "file"
    pass

class DocumentRepository(BaseRepository[Document]):
    """
    Repository for managing documents on the local filesystem.
    """
    model = Document

    def __init__(self, session: AsyncSession):
        # Root folder where all uploads live
        super().__init__(session)
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
        metadata_repository: MetadataRepository,
        file: UploadFile,
        filename: str,
        folder: Optional[str],
        contents: bytes,
        file_type: str,
        user: TokenData,
        file_path: Optional[str] = None,
    ) -> Dict[str, Any]:
        
        rel_folder = Path(user.id) / folder if folder else Path(user.id)
        abs_folder = self.upload_root / rel_folder
        abs_folder.mkdir(parents=True, exist_ok=True)

        extension = SUPPORTED_FILE_TYPES[file_type]
        disk_filename = f"{ULID()}.{extension}"
        abs_path = abs_folder / disk_filename

        abs_path.write_bytes(contents)
        logger.info("Saved new file to %s", abs_path)

        rel_path = str(rel_folder / disk_filename)
        new_doc = Document(
            tenant_id=user.tenant_id,
            department_id=user.department_id,
            owner_id=user.id,
            
            document_number=str(ULID()),
            title=filename,
            name=filename,
            file_type=file_type,
            status= DocStatus.draft,
            file_path=rel_path,
        )
        metadata_repository.session.add(new_doc)
        await metadata_repository.session.flush()

        metadata_repository.session.add(
            DocumentVersion(
                document_id=new_doc.id,
                version_number=1,
                file_path=rel_path,
            )
        )
        await metadata_repository.session.flush()

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
        existing_doc: Document,
        file: UploadFile,
        contents: bytes,
        file_type: str,
        new_file_hash: str,
        is_owner: bool,
        *,
        tenant_id: int,
        department_id: int,
    ) -> Dict[str, Any]:
        # Overwrite the existing file on disk
        rel_path = Path(doc["file_path"])
        abs_path = self.upload_root / existing_doc.file_path 
        abs_path.write_bytes(contents)
        logger.info("Overwrote existing file at %s", abs_path)
        # compute next version number
        result = await self.session.execute(
            select(func.max(DocumentVersion.version_number))
            .where(DocumentVersion.document_id == existing_doc.id)
        )
        latest = result.scalar() or 1
        next_v = latest + 1
        existing_doc.tenant_id = tenant_id
        existing_doc.department_id = department_id

        self.session.add(
            DocumentVersion(
                document_id    = existing_doc.id,
                version_number = next_v,
                file_path      = existing_doc.file_path,

            )
        )
        await self.session.flush()
        return {
            "response": "file_updated",
            "is_owner": is_owner,
            "upload": {
                "name": file.filename,
                "file_path": str(rel_path),
                "size": len(contents),
                "file_type": file_type,
                "file_hash": new_file_hash,
                "version_no":  next_v
            },
        }

    async def upload(
        self,
        metadata_repository: MetadataRepository,
        user_repository: AuthRepository,
        file: UploadFile,
        folder: Optional[str],
        user: TokenData,
        tenant_id: int,
        department_id: int,
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
            existing_doc = (await metadata_repository.get(document=file.filename, owner=user))
            if existing_doc:
                # content changed → new version
                return await self._upload_new_version(
                    existing_doc=existing_doc,
                    file=file,
                    contents=contents,
                    tenant_id=tenant_id,
                    department_id=department_id,
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
            return await self._upload_new_file(
                metadata_repository=metadata_repository,
                file=file,
                folder=folder,
                contents=contents,
                file_type=file_type,
                user=user,
            )

    async def download(
        self,
        document_id: int,
        metadata_repo: MetadataRepository,
        user: TokenData,
    ) -> FileResponse:
        # Prefer the repo method if you added it; otherwise fall back to our helper
        try:
            get_by_id_visible = getattr(metadata_repo, "get_by_id_visible", None)
            meta: Document = (
                await get_by_id_visible(document_id, user)
                if callable(get_by_id_visible)
                else await self._get_meta_visible(document_id, user)
            )
        except Exception:
            logger.error("Download failed, document not found: %s", document_id)
            raise http_404(msg=f"No document with id '{document_id}' found.")

        # FOLDER ⇒ ZIP
        if meta.file_type == "folder":
            tmpdir = tempfile.mkdtemp(prefix="dl-")
            zippath = Path(tmpdir) / f"{meta.name}.zip"

            # Open once, write many
            with zipfile.ZipFile(zippath, "w", zipfile.ZIP_DEFLATED) as zipf:

                async def add_recursive(folder_id: int, prefix: str = ""):
                    # `list_children` is scoped to `user`'s tenant and department,
                    # so the ZIP cannot reach outside them — which is what the
                    # note that used to sit here was asking for.
                    kids = await metadata_repo.list_children(
                        user=user, parent_id=folder_id
                    )
                    for child in kids:
                        if child.file_type == "folder":
                            await add_recursive(child.id, prefix + child.name + "/")
                        else:
                            try:
                                child_path = await get_file_path(child.file_path)
                            except FileNotFoundError:
                                logger.warning("File missing on disk: %s", child.file_path)
                                continue
                            zipf.write(child_path, arcname=prefix + child.name)

                await add_recursive(meta.id)

            # Clean temp dir after response is sent
            return FileResponse(
                zippath,
                filename=f"{meta.name}.zip",
               background=BackgroundTask(shutil.rmtree, tmpdir, ignore_errors=True),
            )

        # FILE ⇒ stream
        try:
            path = await get_file_path(meta.file_path)
        except FileNotFoundError as e:
            logger.error("Download failed, file not found on disk: %s", meta.file_path)
            raise http_404(msg=str(e)) from e

        return FileResponse(path, filename=meta.name)

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
