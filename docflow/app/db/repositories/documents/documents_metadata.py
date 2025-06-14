from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Union
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select, update, insert, delete
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.exceptions import http_409, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.tables.documents.documents_metadata import DocumentMetadata, doc_user_access
from app.db.tables.base_class import StatusEnum
from app.schemas.auth.bands import TokenData
from app.schemas.documents.bands import DocumentMetadataPatch
from app.schemas.documents.documents_metadata import (
    DocumentMetadataCreate,
    DocumentMetadataRead,
)
from app.schemas.documents.documents_metadata import FolderCreate, FolderRead



class DocumentMetadataRepository:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doc_cls = aliased(DocumentMetadata, name="doc_cls")

    async def _get_instance(self, document: Union[str, UUID], owner: TokenData):

        try:
            UUID(str(document))
            stmt = (
                select(self.doc_cls)
                .where(self.doc_cls.owner_id == owner.id)
                .where(self.doc_cls.id == document)
                .where(self.doc_cls.status != StatusEnum.deleted)
            )
        except ValueError:
            stmt = (
                select(self.doc_cls)
                .where(self.doc_cls.owner_id == owner.id)
                .where(self.doc_cls.name == document)
                .where(self.doc_cls.status != StatusEnum.deleted)
            )

        result = await self.session.execute(stmt)

        return result.scalar_one_or_none()

    @staticmethod
    async def _extract_changes(document_patch: DocumentMetadataPatch) -> dict:

        if isinstance(document_patch, dict):
            return document_patch
        return document_patch.model_dump(exclude_unset=True)

    async def _execute_update(
        self, db_document: DocumentMetadata | Dict[str, Any], changes: dict
    ) -> None:

        if isinstance(db_document, dict):
            stmt = (
                update(DocumentMetadata)
                .where(DocumentMetadata.id == db_document.get("id"))
                .values(changes)
            )
            doc_name = db_document.get("name")
        else:
            stmt = (
                update(DocumentMetadata)
                .where(DocumentMetadata.id == db_document.id)
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
            select(DocumentMetadata)
            .where(DocumentMetadata.name == filename)
            .where(self.doc_cls.status != StatusEnum.deleted)
        )
        result = await self.session.execute(stmt)
        result.fetchall()

        return result.scalar_one_or_none()

    async def upload(
        self, document_upload: DocumentMetadataCreate
    ) -> DocumentMetadataRead:

        if not isinstance(document_upload, dict):
            db_document = DocumentMetadata(**document_upload.model_dump())
        else:
            db_document = DocumentMetadata(**document_upload)

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
            .join(DocumentMetadata, DocumentMetadata.id == self.doc_cls.id)
            .where(DocumentMetadata.owner_id == owner.id)
            .where(DocumentMetadata.status != StatusEnum.deleted)
            .offset(offset)
            .limit(limit)
        )

        result = await self.session.execute(stmt)
        result_list = result.fetchall()

        for row in result_list:
            row.doc_cls.__dict__.pop("_sa_instance_state", None)

        result = [
            DocumentMetadataRead(**row.doc_cls.__dict__) for row in result_list
        ]
        # Always return a consistent response, even if empty
        return {f"documents of {owner.username}": result, "no_of_docs": len(result)}

    async def get(
        self, document: Union[str, UUID], owner: TokenData
    ) -> Union[DocumentMetadataRead, HTTPException]:

        db_document = await self._get_instance(document=document, owner=owner)
        if db_document is None:
            return http_409(msg=f"No Document with {document}")

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

            setattr(db_document, "status", StatusEnum.deleted)
            setattr(db_document, "tags", None)
            setattr(db_document, "access_to", None)
            setattr(db_document, "file_type", None)
            setattr(db_document, "categories", None)
            # considering created_at as delete_at to delete it after 30 days
            setattr(
                db_document,
                "created_at",
                datetime.now(timezone.utc) + timedelta(days=30),
            )

            # delete entry from doc_user_access table
            await self._delete_access(document=db_document)

            self.session.add(db_document)

            await self.session.commit()
        except Exception as e:
            raise http_404(msg=f"No file with {document}") from e

    async def bin_list(self, owner: TokenData) -> dict:

        stmt = (
            select(DocumentMetadata)
            .where(DocumentMetadata.owner_id == owner.id)
            .where(DocumentMetadata.status == StatusEnum.deleted)
        )
        result = await self.session.scalars(stmt)
        docs = [DocumentMetadataRead.from_orm(doc) for doc in result]
        return {"response": docs, "no_of_docs": len(docs)}

    async def restore(self, file: str, owner: TokenData) -> DocumentMetadataRead:

        doc_list = await self.bin_list(owner=owner)

        if doc_list["no_of_docs"] > 0:
            for doc in doc_list["response"]:
                if doc.name == file:
                    change = {"status": StatusEnum.private}
                    await self._execute_update(
                        db_document=doc, changes=change
                    )
                    return DocumentMetadataRead(**doc.__dict__)
            raise http_409(msg="Doc is not deleted")
        raise http_404(msg="Doc does not exists")

    async def perm_delete_a_doc(self, document: UUID | None, owner: TokenData) -> None:

        stmt = (
            delete(DocumentMetadata)
            .where(DocumentMetadata.owner_id == owner.id)
            .where(DocumentMetadata.id == document)
            .where(DocumentMetadata.status == StatusEnum.deleted)
        )

        await self.session.execute(stmt)

    async def empty_bin(self, owner: TokenData):

        stmt = (
            delete(DocumentMetadata)
            .where(DocumentMetadata.owner_id == owner.id)
            .where(DocumentMetadata.status == StatusEnum.deleted)
        )

        await self.session.execute(stmt)

    async def archive(self, file: str, user: TokenData):

        doc = await self._get_instance(document=file, owner=user)

        if doc and doc.status != StatusEnum.archived:
            change = {"status": StatusEnum.archived}
            await self._execute_update(db_document=doc, changes=change)
            return DocumentMetadataRead(**doc.__dict__)

        if doc and doc.status == StatusEnum.archived:
            raise http_409(msg="Документ уже в архиве")

        raise http_404(msg="Документ не существует")

    async def archive_list(self, user: TokenData) -> Dict[str, List[str] | int]:

        stmt = (
            select(DocumentMetadata)
            .where(DocumentMetadata.owner_id == user.id)
            .where(DocumentMetadata.status == StatusEnum.archived)
        )

        result = (await self.session.execute(stmt)).fetchall()
        return {"response": result, "no_of_docs": len(result)}

    async def un_archive(self, file: str, user: TokenData) -> DocumentMetadataRead:

        doc = await self._get_instance(document=file, owner=user)

        if doc and doc.status == StatusEnum.archived:
            change = {"status": "private"}
            await self._execute_update(db_document=doc, changes=change)
            return DocumentMetadataRead(**doc.__dict__)
        if doc and doc.status != StatusEnum.archived:
            raise http_409(msg="Doc is not archived")
        raise http_404(msg="Doc does not exits")

    async def create_folder(self, owner_id: str, data: FolderCreate) -> FolderRead:
        folder = DocumentMetadata(
            owner_id=owner_id,
            name=data.name,
            type="folder",
            parent_id=data.parent_id,
        )
        self.session.add(folder)
        await self.session.commit()
        await self.session.refresh(folder)
        return FolderRead.from_orm(folder)

    async def list_children(self, owner_id: str, parent_id: UUID = None) -> List[FolderRead]:
        q = (
            await self.session.execute(
                select(DocumentMetadata)
                .where(DocumentMetadata.owner_id == owner_id)
                .where(DocumentMetadata.parent_id == parent_id)
            )
        )
        results = q.scalars().all()
        return [FolderRead.from_orm(r) for r in results]

    async def archive_document(self, document_id: UUID):
        stmt = update(DocumentMetadata).where(DocumentMetadata.id == document_id).values(is_archived=True)
        await self.session.execute(stmt)
        await self.session.commit()

    async def is_document_archived(self, document_id: UUID) -> bool:
        stmt = select(DocumentMetadata.is_archived).where(DocumentMetadata.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle_starred(self, document_id: UUID):
        stmt = select(DocumentMetadata.is_starred).where(DocumentMetadata.id == document_id)
        result = await self.session.execute(stmt)
        is_starred = result.scalar_one_or_none()

        stmt = update(DocumentMetadata).where(DocumentMetadata.id == document_id).values(is_starred=not is_starred)
        await self.session.execute(stmt)
        await self.session.commit()

    async def archive(self, file: str, user: TokenData):
        doc = await self._get_instance(document=file, owner=user)
        if not doc:
            raise http_404(msg="Document not found")
        if doc.is_archived:
            raise http_409(msg="Document is already archived")
        doc.is_archived = True
        await self.session.commit()
        return DocumentMetadataRead.from_orm(doc)

    async def un_archive(self, file: str, user: TokenData):
        doc = await self._get_instance(document=file, owner=user)
        if not doc:
            raise http_404(msg="Document not found")
        if not doc.is_archived:
            raise http_409(msg="Document is not archived")
        doc.is_archived = False
        await self.session.commit()
        return DocumentMetadataRead.from_orm(doc)

    async def archive_list(self, user: TokenData):
        stmt = select(DocumentMetadata).where(DocumentMetadata.owner_id == user.id).where(DocumentMetadata.is_archived == True)
        result = (await self.session.execute(stmt)).scalars().all()
        return {"documents": [DocumentMetadataRead.from_orm(doc) for doc in result], "count": len(result)}

    async def toggle_starred(self, document_id: UUID, user: TokenData):
        doc = await self._get_instance(document=document_id, owner=user)
        if not doc:
            raise http_404(msg="Document not found")
        doc.is_starred = not doc.is_starred
        await self.session.commit()
        return {"message": "Starred status toggled successfully."}