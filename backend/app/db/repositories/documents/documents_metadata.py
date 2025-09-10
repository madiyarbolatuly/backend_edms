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
from pathlib import Path, PurePosixPath
import hashlib
from typing import List, Optional
from fastapi import UploadFile
from app.schemas.documents.documents_metadata import FolderCreate, FolderRead
from app.db.tables.documents.permissions import Permission, AccessLevel
from app.db.tables.documents.permissions import doc_user_access
from enum import Enum
from app.core.config import settings
from app.db.models import logger
from sqlalchemy.orm import aliased
from sqlalchemy import select, update, insert, delete, func
from pathlib import PurePosixPath, Path

async def _join_posix(a: str | None, b: str | None) -> str:
        """
        Join 2 posix segments without duplicate slashes.
        If a is falsy, returns b. If b is falsy, returns a. 
        """
        a = (a or "").strip("/")
        b = (b or "").strip("/")
        if not a: 
            return b
        if not b:
            return a
        return f"{a}/{b}"

async def _get_base_parent(self, base_parent_id: int | None, user: TokenData) -> Document | None:
        if base_parent_id is None:
            return None
        q = (
            select(Document)
            .where(Document.id == base_parent_id)
            .where(Document.tenant_id == user.tenant_id)
            .where(Document.department_id == user.department_id)
            .where(Document.status != DocStatus.deleted)
            .where(Document.file_type == "folder")
        )
        return (await self.session.execute(q)).scalars().first()

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
        
    async def _find_existing(self, filename: str, user: TokenData, parent_id: Optional[int]) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(Document.tenant_id == user.tenant_id)
            .where(Document.department_id == user.department_id)
            .where(Document.title == filename)
            .where(Document.deleted_at.is_(None))
        )
        if parent_id is None:
            stmt = stmt.where(Document.parent_id.is_(None))
        else:
            stmt = stmt.where(Document.parent_id == parent_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()
    async def _create_or_update_document(
        self,
        *,
        file: UploadFile,
        filename: str,
        file_path: str,
        file_hash: str,
        user: TokenData,
        existing: Optional[Document],
        parent_id: Optional[int] = None,
        ) -> Document:
            if existing:
                values = dict(
                    file_path=file_path,
                    file_hash=file_hash,
                    created_at=datetime.now(timezone.utc),
                    is_archived=False,
                    deleted_at=None,
                )
                if parent_id is not None and parent_id != existing.parent_id:
                    values["parent_id"] = parent_id

                stmt = (
                    update(Document)
                    .where(Document.id == existing.id)
                    .values(**values)
                    .returning(Document)
                )
                result = await self.session.execute(stmt)
                return result.scalar_one()

            new_doc = Document(
                name=filename,
                title=filename,
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

    async def get_by_id_visible(self, doc_id: int, user: TokenData) -> Document:
        q = (
            select(Document)
            .where(
                Document.id == doc_id,
                Document.tenant_id == user.tenant_id,
                Document.department_id == user.department_id,
                # not deleted; tweak if you use another flag/enum
                Document.deleted_at.is_(None),
            )
        )
        doc = (await self.session.execute(q)).scalar_one_or_none()
        if not doc:
            raise http_404(msg=f"No document with id '{doc_id}' found.")
        return doc
   # repo
    async def list_children(
        self, owner_id: str, parent_id: Optional[int] = None, recursive: bool = False
    ) -> List[DocumentMetadataRead]:
        if not recursive:
            q = await self.session.execute(
                select(Document)
                .where(Document.owner_id == owner_id)
                .where(Document.parent_id == parent_id)
            )
            return [DocumentMetadataRead.from_orm(r) for r in q.scalars().all()]

        # Recursive CTE
        doc_alias = aliased(Document)
        base = select(Document).where(Document.owner_id == owner_id).where(Document.parent_id == parent_id)
        recursive = select(Document).join(doc_alias, Document.parent_id == doc_alias.id)
        cte = base.union_all(recursive).cte(name="recursive_children", recursive=True)

        result = await self.session.execute(select(cte))
        return [DocumentMetadataRead.from_orm(d) for d in result.scalars().all()]


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

   


    async def _stream_and_hash(self, file: UploadFile, *, rel_file_path: str, user: TokenData):
        upload_root = Path(settings.upload_dir)
        base_dir = upload_root / str(user.tenant_id) / str(user.department_id)

        file_path = base_dir / rel_file_path
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
        await file.seek(0)

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
        self,
        owner: TokenData,
        parent_id: Optional[int] = None,
        recursive: bool = False,
        only_folders: bool = False,
        files_only: bool = False,        # ← NEW
        limit: int = 100,
        offset: int = 0,
    ):
        # Guard: both flags at once is ambiguous
        if only_folders and files_only:
            files_only = False  # or raise ValueError("only_folders and files_only are mutually exclusive")

        base = (
            select(Document)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
        )

        # Kind filter
        if only_folders:
            base = base.where(Document.file_type == "folder")
        elif files_only:
            # adapt to your model: either `is_folder = False` or file_type != "folder"
            base = base.where(Document.file_type != "folder")

        if not recursive:
            # Current level only
            if parent_id is None:
                base = base.where(Document.parent_id.is_(None))
            else:
                base = base.where(Document.parent_id == parent_id)

            # Count first
            count_stmt = base.with_only_columns(func.count()).order_by(None)
            total_count = (await self.session.execute(count_stmt)).scalar_one()

            # Page
            stmt = base.offset(offset).limit(limit)
            docs = (await self.session.execute(stmt)).scalars().all()

            return {
                "documents": [DocumentMetadataRead.model_validate(doc, from_attributes=True) for doc in docs],
                "total_count": int(total_count),
            }

        # Recursive branch
        parent_filter = (
            Document.parent_id.is_(None) if parent_id is None else Document.parent_id == parent_id
        )

        # re-apply base with same filters (tenant/department/status + kind + parent)
        base = (
            select(Document)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
            .where(parent_filter)
        )
        if only_folders:
            base = base.where(Document.file_type == "folder")
        elif files_only:
            base = base.where(Document.file_type != "folder")

        doc_alias = aliased(Document)

        recursive_q = (
            select(Document)
            .join(doc_alias, Document.parent_id == doc_alias.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
        )

        if only_folders:
            recursive_q = recursive_q.where(Document.file_type == "folder")
        elif files_only:
            recursive_q = recursive_q.where(Document.file_type != "folder")

        cte = base.union_all(recursive_q).cte(name="recursive_docs", recursive=True)

        rows_stmt = (
            select(Document)
            .join(cte, Document.id == cte.c.id)
            .offset(offset)
            .limit(limit)
        )

        count_from = (
            select(Document)
            .join(cte, Document.id == cte.c.id)
            .order_by(None)
            .subquery()
        )
        count_stmt = select(func.count()).select_from(count_from)
        total = (await self.session.execute(count_stmt)).scalar_one()

        docs = (await self.session.execute(rows_stmt)).scalars().all()

        return {
            "documents": [DocumentMetadataRead.model_validate(doc, from_attributes=True) for doc in docs],
            "total_count": int(total),
        }


    async def list_folders(self, owner: TokenData):
        q = (
            select(self.doc_cls.id, self.doc_cls.name, self.doc_cls.parent_id)
            .where(self.doc_cls.is_folder.is_(True))
            # add tenant / ACL filters here as you do elsewhere
            .order_by(self.doc_cls.parent_id.nullsfirst(), self.doc_cls.name)
        )
        rows = (await self.session.execute(q)).all()
        return {"folders": [{"id": r[0], "name": r[1], "parent_id": r[2]} for r in rows]}


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
            # This condition will be activated when, the new version of file is added by a privileged member # here privileged member is one who have access to update the document.
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
            raise http_409(msg="Document is not deleted")
        raise http_404(msg="Document does not exists")

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
            raise http_409(msg="Document is not archived")
        raise http_404(msg="Document does not exits")

   

    async def create_folder(
        self,
        owner_id: str,
        tenant_id: int,
        department_id: Optional[int],
        data: FolderCreate,
    ):
        folder_name = (data.name or "").strip()
        if not folder_name:
            raise ValueError("Folder name is required")

        # вычисляем file_path для папки
        parent_path = ""
        if data.parent_id:
            parent = await self.session.get(Document, data.parent_id)
            if not parent:
                raise ValueError("Parent folder not found")
            # Берём путь родителя (если по каким-то причинам пустой — fallback на имя)
            parent_path = (parent.file_path or parent.name or "").strip()

        def join_path(a: str, b: str) -> str:
            if not a:
                return b
            if a.endswith("/"):
                a = a[:-1]
            return f"{a}/{b}"

        file_path = join_path(parent_path, folder_name) if parent_path else folder_name

        folder = Document(
            owner_id=owner_id,
            tenant_id=tenant_id,
            department_id=department_id,
            file_type="folder",
            document_number=None,          # или генерируй, если нужно
            title=getattr(data, "title", None) or folder_name,
            name=folder_name,
            status="draft",
            file_path=file_path,           # <-- БОЛЬШЕ НЕ NULL
            file_hash=None,
            parent_id=data.parent_id,
        )

        self.session.add(folder)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(folder)
        return folder

  

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

    async def favorited_list(self, user: TokenData):
        stmt = (
            select(Document)
            .where(Document.owner_id == user.id)
            .where(
                (Document.is_favourited  == True) | 
                (Document.status == DocStatus.public)
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
        self,
        folder_paths: list[str],
        *,
        tenant_id,
        user_id,
        department_id,
        base_parent_id: int | None = None,
        user: TokenData | None = None,              # optional (for convenience)
    ) -> dict[str, int]:
        # Normalize to posix
        folder_paths = [PurePosixPath(p).as_posix().strip("/") for p in folder_paths]

        base_parent: Document | None = None
        base_prefix = ""
        if base_parent_id:
            base_parent = await self.session.get(Document, base_parent_id)
            if not base_parent or base_parent.file_type != "folder":
                raise HTTPException(status_code=404, detail="Target folder not found")
            base_prefix = (base_parent.file_path or base_parent.name or "").strip("/")

        final_paths: list[str] = []
        for p in folder_paths:
            final_paths.append(await _join_posix(base_prefix, p) if base_prefix else p)

        # Preload existing
        existing = await self.get_existing_folders(final_paths, tenant_id)
        path_to_id: dict[str, int] = {f.file_path: f.id for f in existing}

        # Create in topological order
        for rel_path in sorted(folder_paths):
            final_path = await _join_posix(base_prefix, rel_path) if base_prefix else rel_path
            if final_path in path_to_id:
                continue

            parent_rel = "/".join(rel_path.split("/")[:-1]) if "/" in rel_path else None
            parent_final = await _join_posix(base_prefix, parent_rel) if parent_rel else base_prefix or None
            
            if not parent_rel and base_parent_id:
                parent_id = base_parent_id
            else:
                parent_id = path_to_id.get(parent_final)
            name = rel_path.split("/")[-1]

            folder = Document(
                name=name,
                title=name,
                file_type="folder",
                parent_id=parent_id,
                tenant_id=tenant_id,
                department_id=department_id,
                owner_id=user_id,
                status=DocStatus.private,
                is_archived=False,
                is_favourited=False,
                file_path=final_path,  # ← IMPORTANT
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(folder)
            await self.session.flush()
            path_to_id[final_path] = folder.id

        return path_to_id



    # documents_metadata.py

    async def upload_with_streaming(
        self,
        *,
        file: UploadFile,
        folder: str | None,            # relative path from the browser (webkitRelativePath's folder part)
        filename: str,
        user: TokenData,
        parent_map: dict[str, int],    # maps FINAL folder paths to IDs (from bulk_create_folders)
        base_parent_id: int | None = None,
    ):
        # Load base parent to get its prefix path
        base_parent = await _get_base_parent(self, base_parent_id, user)
        base_prefix = (base_parent.file_path or base_parent.name or "").strip("/") if base_parent else ""

        # Normalize incoming folder
        folder = PurePosixPath(folder or "").as_posix().strip("/")

        # Compute the FINAL logical folder path we will store in DB
        final_folder_path = await _join_posix(base_prefix, folder) if folder else base_prefix

        # Full logical path (what you keep in DB `file_path`)
        rel_file_path = (
            await _join_posix(final_folder_path, filename) if final_folder_path else filename
        )

        # Stream bytes to that exact location on disk
        file_hash, file_size, stored_rel_path = await self._stream_and_hash(
            file, rel_file_path=rel_file_path, user=user
        )

        # Lookup parent_id by FINAL folder path (empty means root OR selected base parent)
        if final_folder_path:
            parent_id = parent_map.get(final_folder_path)
        else:
            parent_id = base_parent_id  # put file directly under the selected folder if present

        existing = await self._find_existing(filename, user, parent_id)
        if existing and existing.file_hash == file_hash:
            return {"response": "no_change", "document": existing}

        document = await self._create_or_update_document(
            file=file,
            filename=filename,
            file_path=stored_rel_path, 
            file_hash=file_hash,
            user=user,
            existing=existing,
            parent_id=parent_id,
        )
        return {"response": "success", "document": document}
