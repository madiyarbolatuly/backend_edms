from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
import hashlib
from random import randint

from app.db.tables.documents.shared import SharedDocument
from app.db.tables.documents.documents import Document
from app.db.tables.auth.auth import User
from app.core.exceptions import http_403, http_404


class SharedDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _generate_token(self, source: str) -> str:
        """Создаёт короткий 6-символьный токен на основе md5"""
        digest = hashlib.md5(source.encode("utf-8")).hexdigest()
        start = randint(0, len(digest) - 6)
        return digest[start:start+6]

    async def create_share_records(
        self,
        owner_id,
        doc_ids: List[int],
        shared_with_id: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> None:
        """
        Добавляет записи о шаринге файлов/папок в таблицу shared_documents.
        """
        now = datetime.now(timezone.utc)
        effective_exp = expires_at or (now + timedelta(days=7))

        docs = (
            await self.session.execute(
                select(Document).where(Document.id.in_(doc_ids))
            )
        ).scalars().all()

        for d in docs:
            token = self._generate_token(f"{d.name}{shared_with_id}{now.isoformat()}")
            self.session.add(
                SharedDocument(
                    document_id=d.id,
                    shared_by=owner_id,
                    shared_with=shared_with_id or owner_id,
                    token=token,
                    filename=d.name,
                    expires_at=effective_exp,
                )
            )

        await self.session.commit()

    async def list_shared_by_user(self, user_id: str) -> List[SharedDocument]:
        """
        Возвращает все документы, расшаренные текущим пользователем.
        """
        res = await self.session.execute(
            select(SharedDocument).where(SharedDocument.shared_by == user_id)
        )
        return res.scalars().all()

    async def list_shared_with_user(self, user_id: str) -> List[SharedDocument]:
        """
        Возвращает все документы, расшаренные другим пользователем для этого пользователя.
        """
        res = await self.session.execute(
            select(SharedDocument).where(SharedDocument.shared_with == user_id)
        )
        return res.scalars().all()

    async def list_shared_with_user_rich(self, user_id: str) -> List[Tuple[SharedDocument, Optional[str], Optional[str], Optional[str]]]:
        """Return shares for user with resolved shared_by username/email and document file_path."""
        q = (
            select(SharedDocument, User.username, User.email, Document.file_path)
            .join(User, User.id == SharedDocument.shared_by)
            .join(Document, Document.id == SharedDocument.document_id)
            .where(SharedDocument.shared_with == user_id)
            .order_by(SharedDocument.expires_at.asc().nulls_last(), SharedDocument.created_at.desc())
        )
        res = await self.session.execute(q)
        return res.all()

    async def list_shared_by_user_rich(self, user_id: str) -> List[Tuple[SharedDocument, Optional[str], Optional[str], Optional[str]]]:
        q = (
            select(SharedDocument, User.username, User.email, Document.file_path)
            .join(User, User.id == SharedDocument.shared_with)
            .join(Document, Document.id == SharedDocument.document_id)
            .where(SharedDocument.shared_by == user_id)
            .order_by(SharedDocument.expires_at.asc().nulls_last(), SharedDocument.created_at.desc())
        )
        res = await self.session.execute(q)
        return res.all()

    async def get_share(self, share_id: int) -> SharedDocument:
        share = await self.session.get(SharedDocument, share_id)
        if not share:
            raise http_404(msg="Share not found")
        return share

    async def update_share(
        self,
        *,
        share_id: int,
        actor_id: str,
        filename: Optional[str] = None,
        expires_at: Optional[datetime] = None,
    ) -> SharedDocument:
        share = await self.get_share(share_id)
        if share.shared_by != actor_id:
            raise http_403(msg="Only owner can update share")

        changes = {}
        if filename is not None and filename.strip():
            changes["filename"] = filename.strip()
        if expires_at is not None:
            changes["expires_at"] = expires_at

        if not changes:
            return share

        await self.session.execute(
            update(SharedDocument).where(SharedDocument.id == share_id).values(**changes)
        )
        await self.session.commit()
        return await self.get_share(share_id)

    async def delete_share(self, *, share_id: int, actor_id: str) -> None:
        share = await self.get_share(share_id)
        if share.shared_by != actor_id:
            raise http_403(msg="Only owner can delete share")

        await self.session.execute(delete(SharedDocument).where(SharedDocument.id == share_id))
        await self.session.commit()
