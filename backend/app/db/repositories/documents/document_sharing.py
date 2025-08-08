import hashlib
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from random import randint
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile

from app.api.dependencies.mail_service import mail_service
from app.api.dependencies.repositories import get_file_path
from app.core.config import settings
from app.core.exceptions import http_404, http_500
from app.db.tables.auth.auth import User
from app.db.tables.documents.shared import SharedDocument
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.notify import NotifyRepo
from app.schemas.auth.bands import TokenData
from app.schemas.documents.document_sharing import SharingRequest
from app.db.tables.documents.documents import Document

from sqlalchemy import select, delete
from uuid import UUID

async def _get_document(session: AsyncSession, filename: str) -> Document:
    from app.db.tables.documents.documents import Document
    stmt = select(Document).where(Document.name == filename)
    doc = (await session.execute(stmt)).scalar_one_or_none()
    if not doc:
        raise http_404(msg="Документ не найден.")
    return doc

class SharedDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _generate_token(source: str) -> str:
        digest = hashlib.md5(source.encode("utf-8")).hexdigest()
        return digest[randint(0, len(digest) - 6):][:6]

    async def _existing_link(
        self, doc_id: int, shared_with: str
    ) -> Optional[SharedDocument]:
        stmt = (
            select(SharedDocument)
            .where(SharedDocument.document_id == doc_id)
            .where(SharedDocument.shared_with == shared_with)
            .where(SharedDocument.expires_at > datetime.now(timezone.utc))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def _purge_expired(self) -> None:
        now = datetime.now(timezone.utc)
        stmt = delete(SharedDocument).where(SharedDocument.expires_at <= now)
        await self.session.execute(stmt)

    async def get_shareable_link(
        self,
        owner: TokenData,             
        filename: str,
        share_to: List[str],
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Для каждого получателя либо возвращает уже существующую ссылку,
        либо создаёт новую запись в `shared_documents`.
        """
        await self._purge_expired()
        from app.db.tables.documents.documents import Document
        stmt = select(Document).where(Document.name == filename)
        doc = (await self.session.execute(stmt)).scalar_one_or_none()
        if not doc:
            raise http_404(msg="Документ не найден.")
        doc_id = doc.id



        links: Dict[str, str] = {}
        for recipient in share_to:
            entry = await self._existing_link(doc_id, recipient)
            if entry is None:
                token = self._generate_token(f"{filename}{recipient}{datetime.utcnow()}")
                entry = SharedDocument(
                    document_id=doc_id,
                    shared_by=owner.id,
                    shared_with=recipient,
                    token=token,
                    filename=doc.name,  
                    expires_at= expires_at or datetime.now(timezone.utc) + timedelta(days=7),
                   
                )
                self.session.add(entry)

            links[recipient] = (
                f"{settings.host_url}{settings.api_prefix}/doc/{entry.token}"
            )

        await self.session.commit()
        return {
            "links": links,                
            "expires_at": expires_at,
        }

    async def get_redirect_url(self, token: str) -> str:
        entry = (
            await self.session.execute(
                select(SharedDocument).where(SharedDocument.token == token)
            )
        ).scalar_one_or_none()
        if entry is None or entry.expires_at <= datetime.now(timezone.utc):
            raise http_404(msg="Ссылка недействительна или истекла.")
        return f"{settings.host_url}/uploads/{token}"

    async def confirm_access(self, user: TokenData, token: str) -> bool:
        entry = (
            await self.session.execute(
                select(SharedDocument).where(SharedDocument.token == token)
            )
        ).scalar_one_or_none()
        if not entry:
            return False
        if entry.shared_by == user.id:
            return True
        user_mail = await self.get_user_mail(user)
        return user_mail == entry.shared_with or user.username == entry.shared_with
