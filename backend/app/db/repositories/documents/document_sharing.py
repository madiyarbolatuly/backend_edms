from datetime import datetime, timedelta, timezone
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import hashlib
from random import randint

from app.db.tables.documents.shared import SharedDocument
from app.db.tables.documents.documents import Document


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
