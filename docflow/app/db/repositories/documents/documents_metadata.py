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
from app.db.tables.documents.documents import Document

from app.schemas.documents.documents_metadata import FolderCreate, FolderRead
from app.db.tables.documents.permissions import Permission, AccessLevel
from app.db.tables.documents.permissions import doc_user_access
from enum import Enum

class MetadataRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doc_cls = aliased(Document, name="doc_cls")

    async def _get_instance(self, document: Union[str, UUID], owner: TokenData):

        try:
            UUID(str(document))
            stmt = (
                select(self.doc_cls)
                .where(self.doc_cls.owner_id == owner.id)
                .where(self.doc_cls.tenant_id == owner.tenant_id)
                .where(self.doc_cls.department_id == owner.department_id)
                .where(self.doc_cls.name == document)
                .where(self.doc_cls.deleted_at.is_(None))
            )
        except ValueError:
            stmt = (
                select(self.doc_cls)
                .where(self.doc_cls.owner_id == owner.id)
                .where(self.doc_cls.tenant_id == owner.tenant_id)
                .where(self.doc_cls.department_id == owner.department_id)
                .where(self.doc_cls.name == document)
                # .where(self.doc_cls.status != St  atusEnum.deleted)
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

    async def _update_doc_user_access(self, db_document, user_id):

        stmt = insert(doc_user_access).values(
            doc_id=db_document.__dict__["id"], user_id=user_id
        )
        await self.session.execute(stmt)
        await self.session.commit()

    async def _delete_access(self, document) -> None:
        await self.session.execute(
            doc_user_access.delete().where(doc_user_access.c.doc_id == document.id)
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
            .join(Document, Document.id == self.doc_cls.id)
            .where(Document.owner_id == owner.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
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
            db_document = await self.get_doc(filename=document)
            changes = await self._extract_changes(document_patch)

            if changes:
                await self._execute_update(db_document, changes)

        return DocumentMetadataRead(**db_document.__dict__)

    async def delete(self, document: Union[str, UUID], owner: TokenData) -> None:

        try:
            db_document = await self._get_instance(document=document, owner=owner)

            # setattr(db_document, "status", DocStatus.deleted)
            # setattr(db_document, "tags", None)
            # setattr(db_document, "access_to", None)
            # setattr(db_document, "file_type", None)
            # setattr(db_document, "categories", None)
            # # considering created_at as delete_at to delete it after 30 days
            # setattr(
            #     db_document,
            #     "created_at",
            #     datetime.now(timezone.utc) + timedelta(days=30),
            # )
            db_document.deleted_at = datetime.now(timezone.utc) 

            # delete entry from doc_user_access table
            await self._delete_access(document=db_document)

            self.session.add(db_document)

            await self.session.commit()
        except Exception as e:
            raise http_404(msg=f"No file with {document}") from e

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
                    change = {"status": DocStatus.private}
                    await self._execute_update(
                        db_document=doc, changes=change
                    )
                    return DocumentMetadataRead(**doc.__dict__)
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

    async def empty_bin(self, owner: TokenData):

        stmt = (
            delete(Document)
            .where(Document.owner_id == owner.id)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status == DocStatus.deleted)
        )

        await self.session.execute(stmt)

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

    async def list_children(self, owner_id: str, parent_id: UUID = None) -> List[FolderRead]:
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
        stmt = select(Document).where(Document.owner_id == user.id).where(Document.is_archived == True)
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