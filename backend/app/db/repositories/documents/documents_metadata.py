from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Union
from uuid import UUID
from app.db.tables.documents.versions import DocumentVersion    
from fastapi import HTTPException
from sqlalchemy import select, update, insert, delete
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.core.exceptions import http_409, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.tables.documents.documents import Document
from app.db.tables.base_class import DocStatus
from app.schemas.auth.bands import TokenData
from app.schemas.documents.bands import DocumentMetadataPatch
from app.schemas.documents.documents_metadata import (
    DocumentMetadataCreate,
    DocumentMetadataRead,
)
from app.db.base import BaseRepository
from pathlib import Path
import hashlib
from typing import List, Optional
from fastapi import UploadFile
from app.schemas.documents.documents_metadata import FolderCreate, FolderRead
from app.db.tables.documents.permissions import Permission, AccessLevel
from app.db.tables.documents.permissions import doc_user_access
from enum import Enum
from app.core.config import settings
from app.db.models import logger

class MetadataRepository(BaseRepository[Document]):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doc_cls = aliased(Document, name="doc_cls")

    async def _get_instance(self, document: Union[str, UUID], owner: TokenData):
        try:
            # First try to convert to integer ID (for database IDs like 3)
            document_id = int(str(document))
            stmt = (
                select(self.doc_cls)
                .where(self.doc_cls.owner_id == owner.id)
                .where(self.doc_cls.tenant_id == owner.tenant_id)
                .where(self.doc_cls.department_id == owner.department_id)
                .where(self.doc_cls.id == document_id)  # Search by integer ID
                .where(self.doc_cls.deleted_at.is_(None))
            )
        except ValueError:
            try:
                # If not an integer, try to convert to UUID
                document_id = UUID(str(document))
                stmt = (
                    select(self.doc_cls)
                    .where(self.doc_cls.owner_id == owner.id)
                    .where(self.doc_cls.tenant_id == owner.tenant_id)
                    .where(self.doc_cls.department_id == owner.department_id)
                    .where(self.doc_cls.id == document_id)  # Search by UUID
                    .where(self.doc_cls.deleted_at.is_(None))
                )
            except ValueError:
                # If not a valid UUID either, search by name (with URL decoding)
                from urllib.parse import unquote
                decoded_name = unquote(document)  # Decode URL-encoded filename
                
                stmt = (
                    select(self.doc_cls)
                    .where(self.doc_cls.owner_id == owner.id)
                    .where(self.doc_cls.tenant_id == owner.tenant_id)
                    .where(self.doc_cls.department_id == owner.department_id)
                    .where(self.doc_cls.name == decoded_name)  # Search by decoded name
                    .where(self.doc_cls.deleted_at.is_(None))
                )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _extract_changes(document_patch: DocumentMetadataPatch) -> dict:

        if isinstance(document_patch, dict):
            return document_patch
        return document_patch.model_dump(exclude_unset=True)

    async def _execute_update(
        self, db_document: Document | Dict[str, Any], changes: Dict[str, Any]
    ) -> Document:

        if isinstance(db_document, dict):
            stmt = (
                update(Document)
                .where(Document.id == db_document.get("id"))
                .values(changes)
            )
            doc_name = db_document.get("name")
        else:
            stmt = (
                update(Document)
                .where(Document.id == db_document.id)
                .values(changes)
            )
            doc_name = db_document.name

        try:
            await self.session.execute(stmt)
        except Exception as e:
            raise http_409(msg=f"Ошибка при обновлении документа: {doc_name}") from e
        
    async def _find_existing(self, filename: str, user: TokenData) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(Document.name == filename)
            .where(Document.tenant_id == user.tenant_id)
            .where(Document.department_id == user.department_id)
            .where(Document.owner_id == user.id)
            .where(Document.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
    async def _create_or_update_document(
    self,
    *,
    file: UploadFile,
    file_path: str,
    file_hash: str,
    file_size: int,
    user: TokenData,
    existing: Optional[Document],
    parent_id: Optional[int] = None,
    ) -> Document:
        if existing:
            stmt = (
                update(Document)
                .where(Document.id == existing.id)
                .values(
                    file_path=file_path,
                    file_hash=file_hash,
                    created_at=datetime.now(timezone.utc),
                    is_archived=False,
                    deleted_at=None,
                )
                .returning(Document)
            )
            result = await self.session.execute(stmt)
            return result.scalar_one()

        new_doc = Document(
            name=file.filename,
            title=file.filename,
            tenant_id=user.tenant_id,
            department_id=user.department_id,
            owner_id=user.id,
            file_type="file",
            file_path=file_path,
            file_hash=file_hash,
            created_at=datetime.now(timezone.utc),
            parent_id=parent_id,
        )
        self.session.add(new_doc)
        await self.session.flush()
        return new_doc


    async def _update_access_and_permission(self, db_document, changes, user_repo):

        access_given_to = changes.get("access_to", [])
        # if access_to has email ids, update doc_user_access table with doc_id and user_id
        for user_email in access_given_to:
            try:
                user_id = (
                    await user_repo.get_user(field="email", detail=user_email)
                ).__dict__["id"]
                # update doc_user_access table with doc_id and user_id
                await self._update_doc_user_access(db_document, user_id)

            except IntegrityError as e:
                raise http_409(msg=f"g '{user_email}' уже имеет доступ...") from e
            except AttributeError as e:
                raise http_404(
                    msg=f"Пользователь с адресом '{user_email}' не существует, убедитесь, что у пользователя есть аккаунт в DocFlow."
                ) from e

   

    async def _stream_and_hash(self, file: UploadFile, user: TokenData, folder: Optional[str]):
        upload_root = Path(settings.upload_dir)
        # Base directory for this tenant/department
        base_dir = upload_root / str(user.tenant_id) / str(user.department_id)

        # file.filename already includes any subfolder information (e.g. "folder1/file1.txt")
        relative_path = Path(file.filename)

        # Final path: base_dir + relative path
        file_path = base_dir / relative_path

        # Make sure all parent directories exist
        file_path.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        total_size = 0

        with file_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha256.update(chunk)
                total_size += len(chunk)

        await file.seek(0)  # reset file stream if reused

    # Return path relative to upload_root so it matches your DB schema
        return sha256.hexdigest(), total_size, str(file_path.relative_to(upload_root))


    async def _update_doc_user_access(self, db_document, user_id):

        stmt = insert(doc_user_access).values(
            doc_id=db_document.__dict__["id"], user_id=user_id
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def _delete_access(self, document) -> None:
        await self.session.execute(
            doc_user_access.delete().where(doc_user_access.c.document_id == document.id)
        )

    async def get_doc(self, filename: str) -> Dict[str, Any]:
        """
        Get document by filename irrespective of logged-in user.

        Args:
            self: The instance of the class.
            filename (str): The name of the document.

        Returns:
            Dict[str, Any]: The document metadata.
        """

        stmt = (
            select(Document)
            .where(Document.name == filename)
            .where(Document.deleted_at.is_(None))
            #.where(self.doc_cls.status != DocStatus.deleted)
        )
        result = await self.session.execute(stmt)
        result.fetchall()

        return result.scalar_one_or_none()

    async def upload(
        self, document_upload: DocumentMetadataCreate
    ) -> DocumentMetadataRead:

        if not isinstance(document_upload, dict):
            db_document = Document(**document_upload.model_dump(exclude={"size", "tags", "categories", "file_hash", "access_to", "status"}))
        else:
            db_document = Document(**document_upload)

        try:
            self.session.add(db_document)
            await self.session.commit()
            await self.session.refresh(db_document)
        except IntegrityError as e:
            raise http_404(
                msg=f"Документ с именем: {document_upload.name} уже существует.",
            ) from e

        return DocumentMetadataRead(**db_document.__dict__)

    async def doc_list(
        self, owner: TokenData, limit: int = 10, offset: int = 0
    ) -> Dict[str, Union[List[DocumentMetadataRead], Any]]:

        stmt = (
            select(self.doc_cls)
            .where(self.doc_cls.tenant_id == owner.tenant_id)
            .where(self.doc_cls.status != DocStatus.deleted)
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        result_list = result.scalars().all()

        # Приведение Enum (если нужно)
        for doc in result_list:
            if isinstance(doc.status, Enum) and not isinstance(doc.status, DocStatus):
                doc.status = DocStatus(doc.status.value)

        result_models = [DocumentMetadataRead.model_validate(doc) for doc in result_list]

        return {
            f"documents of {owner.username}": result_models,
            "no_of_docs": len(result_models),
        }

    async def get(
        self, document: Union[str, UUID], owner: TokenData
    ) -> Union[DocumentMetadataRead, HTTPException]:

        db_document = await self._get_instance(document=document, owner=owner)
        if db_document is None:
            raise http_409(msg=f"No Document with {document}")

        return DocumentMetadataRead(**db_document.__dict__)

    async def patch(
        self,
        document: Union[str, UUID],
        document_patch: DocumentMetadataPatch,
        owner: TokenData,
        user_repo: AuthRepository,
        is_owner: bool,
    ) -> Union[DocumentMetadataRead, HTTPException]:

        if is_owner:
            db_document = await self._get_instance(document=document, owner=owner)
            changes = await self._extract_changes(document_patch)

            await self._update_access_and_permission(db_document, changes, user_repo)

            await self._execute_update(db_document, changes)

        else:
            # This condition will be activated when, the new version of file is added by a privileged member
            # here privileged member is one who have access to update the document.
            db_document = await self.get_doc(filename=str(document))
            changes = await self._extract_changes(document_patch)

            if changes:
                await self._execute_update(db_document, changes)

        return DocumentMetadataRead(**db_document.__dict__)

    async def delete(self, document: Union[str, UUID], owner: TokenData) -> None:
        try:
            db_document = await self._get_instance(document=document, owner=owner)
            
            if db_document is None:
                raise http_404(msg=f"No document found with identifier: {document}")
            
            # Set both deleted_at timestamp and status to deleted for consistency
            db_document.deleted_at = datetime.now(timezone.utc)
            db_document.status = DocStatus.deleted
            await self._delete_access(document=db_document)
            self.session.add(db_document)
            await self.session.commit()
            
        except HTTPException:
            # Re-raise HTTP exceptions as-is
            raise
        except Exception as e:
            # Log the actual error for debugging
            logger.error(f"Error deleting document {document}: {str(e)}")
            raise http_404(msg=f"Failed to delete document: {document}") from e

    async def bin_list(self, owner: TokenData) -> dict:

        stmt = (
            select(Document)
            .where(Document.owner_id == owner.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status == DocStatus.deleted)
        )
        result = await self.session.scalars(stmt)
        docs = [DocumentMetadataRead.from_orm(doc) for doc in result]
        return {"response": docs, "no_of_docs": len(docs)}

    async def restore(self, file: str, owner: TokenData) -> DocumentMetadataRead:

        doc_list = await self.bin_list(owner=owner)

        if doc_list["no_of_docs"] > 0:
            for doc in doc_list["response"]:
                if doc.name == file:
                    # Find the deleted document directly from database
                    stmt = (
                        select(Document)
                        .where(Document.id == doc.id)
                        .where(Document.owner_id == owner.id)
                        .where(Document.tenant_id == owner.tenant_id)
                        .where(Document.department_id == owner.department_id)
                        .where(Document.status == DocStatus.deleted)
                    )
                    result = await self.session.execute(stmt)
                    db_document = result.scalar_one_or_none()
                    
                    if db_document:
                        # Clear deleted_at and set status back to private
                        db_document.deleted_at = None
                        db_document.status = DocStatus.private
                        self.session.add(db_document)
                        await self.session.commit()
                        return DocumentMetadataRead(**db_document.__dict__)
            raise http_409(msg="Doc is not deleted")
        raise http_404(msg="Doc does not exists")

    async def perm_delete_a_doc(self, document: UUID | None, owner: TokenData) -> None:

        stmt = (
            delete(Document)
            .where(Document.owner_id == owner.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.id == document)
            .where(Document.status == DocStatus.deleted)
        )

        await self.session.execute(stmt)
        await self.session.commit()

    async def empty_bin(self, owner: TokenData):

        stmt = (
            delete(Document)
            .where(Document.owner_id == owner.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status == DocStatus.deleted)
        )

        await self.session.execute(stmt)
        await self.session.commit()

    async def archive(self, document: str, user: TokenData) -> DocumentMetadataRead:

        doc = await self._get_instance(document=document, owner=user)

        if doc and doc.status != DocStatus.archived:
            change = {"status": DocStatus.archived}
            await self._execute_update(db_document=doc, changes=change)
            return DocumentMetadataRead(**doc.__dict__)

        if doc and doc.status == DocStatus.archived:
            raise http_409(msg="Документ уже в архиве")

        raise http_404(msg="Документ не существует")


    async def un_archive(self, file: str, user: TokenData) -> DocumentMetadataRead:

        doc = await self._get_instance(document=file, owner=user)

        if doc and doc.status == DocStatus.archived:
            change = {"status": "private"}
            await self._execute_update(db_document=doc, changes=change)
            return DocumentMetadataRead(**doc.__dict__)
        if doc and doc.status != DocStatus.archived:
            raise http_409(msg="Doc is not archived")
        raise http_404(msg="Doc does not exits")

    async def create_folder(self, owner_id: str, data: FolderCreate) -> FolderRead:
        folder = Document(
            owner_id=owner_id,
            name=data.name,
            file_type="folder",
            parent_id=data.parent_id,
        )
        self.session.add(folder)
        await self.session.commit()
        await self.session.refresh(folder)
        return FolderRead.from_orm(folder)

    async def list_children(self, owner_id: str, parent_id: Optional[int] = None) -> List[FolderRead]:
        q = (
            await self.session.execute(
                select(Document)
                .where(Document.owner_id == owner_id)
                .where(Document.parent_id == parent_id)
            )
        )
        results = q.scalars().all()
        return [FolderRead.from_orm(r) for r in results]

    async def archive_document(self, document_id: UUID):
        stmt = update(Document).where(Document.id == document_id).values(is_archived=True)
        await self.session.execute(stmt)
        await self.session.commit()

    async def is_document_archived(self, document_id: UUID) -> bool:
        stmt = select(Document.is_archived).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle_favourited(self, document_id: UUID):
        stmt = select(Document.is_favourited).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        is_favourited = result.scalar_one_or_none()

        stmt = update(Document).where(Document.id == document_id).values(is_favourited=not is_favourited)
        await self.session.execute(stmt)
        await self.session.commit()


    async def archive_list(self, user: TokenData):
        stmt = (
            select(Document)
            .where(Document.owner_id == user.id)
            .where(
                (Document.is_archived == True) | 
                (Document.status == DocStatus.archived)
            )
            .where(Document.deleted_at.is_(None))
        )
        
        result = (await self.session.execute(stmt)).scalars().all()
        return {"documents": [DocumentMetadataRead.from_orm(doc) for doc in result], "count": len(result)}



    async def get_folder_by_name_and_parent(self, name: str, parent_id: UUID, owner_id: str):
        stmt = (
            select(Document)
            .where(Document.name == name)
            .where(Document.parent_id == parent_id)
            .where(Document.owner_id == owner_id)
            .where(Document.type == "folder")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_folder_by_id(self, folder_id: UUID, owner_id: str):
        stmt = (
            select(Document)
            .where(Document.id == folder_id)
            .where(Document.parent_id == None )
            .where(Document.owner_id == owner_id)
            .where(Document.type == "folder")
            .where(Document.status != DocStatus.deleted
            )  # Ensure the folder is not deleted   
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()  # <-- Добавь это

    async def get_existing_folders(self, folder_paths: List[str], tenant_id: UUID) -> List[Document]:
        stmt = (
            select(Document)
            .where(Document.file_type == "folder")
            .where(Document.tenant_id == tenant_id)
            .where(Document.file_path.in_(folder_paths))
            .where(Document.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    

        
    async def bulk_create_folders(
        self, folder_paths: List[str], *, tenant_id: UUID, user_id: UUID, department_id: UUID
    ) -> Dict[str, int]:
        existing = await self.get_existing_folders(folder_paths, tenant_id)
        
        # Sort paths to create parent folders first
        sorted_paths = sorted(folder_paths)
        path_to_folder: dict[str, int] = {f.file_path: f.id for f in existing}
        
        for path in sorted_paths:
            if path in path_to_folder:
                continue
            
            # Find parent folder
            parent_path = "/".join(path.split("/")[:-1]) if "/" in path else None
            parent_id = path_to_folder[parent_path] if parent_path and parent_path in path_to_folder else None
            
            folder = Document(
                name=path.split("/")[-1],
                title=path.split("/")[-1],
                status=DocStatus.private,
                is_archived=False,
                is_favourited=False,
                file_path=path,
                tenant_id=tenant_id,
                department_id=department_id,
                owner_id=user_id,
                file_type="folder",
                parent_id=parent_id,
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(folder)
            await self.session.flush()
            path_to_folder[path] = folder.id
        
        return path_to_folder

    async def upload_with_streaming(
        self, *,
        file: UploadFile,
        folder: Optional[str],
        user: TokenData,
        parent_map: dict[str, int]
    ):
        try:
            file_hash, file_size, file_path = await self._stream_and_hash(file, user, folder)
            existing = await self._find_existing(file.filename, user)
            if existing and existing.file_hash == file_hash:
                return {"response": "no_change", "document": existing}
            parent_id = None
            if folder:                      # '' → корень
                parent_id = parent_map.get(folder.rstrip("/"))

            document = await self._create_or_update_document(
                file=file,
                file_path=file_path,
                file_hash=file_hash,
                file_size=file_size,
                user=user,
                existing=existing,
                parent_id=parent_id,        # ← передаём
            )
            return {"response": "success", "document": document}
        except Exception:
            if 'file_path' in locals():
                Path(file_path).unlink(missing_ok=True)
            raise
