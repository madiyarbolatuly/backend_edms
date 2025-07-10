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


class SharedDocumentRepository:
    """
    Repository for managing document‐sharing records and links
    on the local filesystem.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_mail(self, user: TokenData) -> str:
        """
        Lookup the user’s email by their ID.
        """
        stmt = select(User.email).where(User.id == user.id)
        result = await self.session.execute(stmt)
        email = result.scalar_one_or_none()
        if not email:
            raise http_404(msg="Пользователь не найден.")
        return email

    @staticmethod
    async def _generate_id(source: str) -> str:
        """
        Create a 6-char slice of an MD5 hash of the filename (or URL).
        """
        digest = hashlib.md5(source.encode("utf-8")).hexdigest()
        offset = randint(0, len(digest) - 6)
        return digest[offset : offset + 6]

    async def _get_saved_link(self, filename: str) -> Optional[SharedDocument]:
        """
        Check if there’s already a sharing entry for this filename.
        """
        stmt = select(SharedDocument).where(SharedDocument.filename == filename)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def cleanup_expired_links(self) -> None:
        """
        Purge any sharing entries whose expiry has passed.
        """
        now = datetime.now(timezone.utc)
        stmt = delete(SharedDocument).where(SharedDocument.expires_at <= now)
        await self.session.execute(stmt)

    async def get_shareable_link(
        self, owner_id: str, filename: str, visits: int, share_to: List[str], expires_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Return an existing link (if still valid), or create a new one.
        """
        # 1) Remove expired entries first
        await self.cleanup_expired_links()

        # 2) If already shared and still valid, return it
        existing = await self._get_saved_link(filename)
        if existing:
            data = existing.__dict__
            return {
                "note": f"Ссылка действительна до {data['expires_at']}",
                "response": {
                    "shareable_link": (
                        f"{settings.host_url}{settings.api_prefix}/doc/{data['url_id']}"
                    ),
                    "visits_left": data["visits"],
                },
            }

        # 3) Otherwise, create a new sharing entry
        url_id = await self._generate_id(filename)
        expires_at = (
            expires_at
            if expires_at
            else datetime.now(timezone.utc) + timedelta(days=7)
        )

        share_entry = SharedDocument(
            url_id=url_id,
            owner_id=owner_id,
            filename=filename,
            url=f"{settings.host_url}/uploads/{filename}",
            expires_at=expires_at,
            visits=visits,
            share_to=share_to,
        )

        try:
            self.session.add(share_entry)
            await self.session.commit()
            await self.session.refresh(share_entry)
        except Exception as e:
            raise http_500() from e

        return {
            "shareable_link": (
                f"{settings.host_url}{settings.api_prefix}/doc/{share_entry.url_id}"
            ),
            "visits": share_entry.visits,
        }

    async def get_redirect_url(self, url_id: str) -> str:
        """
        Look up the real file URL for a share link, decrement visits,
        or 404 if expired/invalid.
        """
        stmt = select(SharedDocument).where(SharedDocument.url_id == url_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()

        if not record:
            raise http_404(
                msg="Ссылка на документ недействительна или срок ее действия истек."
            )

        # decrement or delete
        return record.url

    async def send_mail(
        self,
        user: TokenData,
        mail_to: Union[List[str], None],
        link: str
    ) -> None:
        """
        Optionally email the shareable link to a list of recipients.
        """
        if not mail_to:
            return

        sender_email = await self.get_user_mail(user)
        subject = f"GQ Group: {user.username} поделился с документом"
        body = (
            f"Здравствуйте,\n\n"
            f"{user.username} ({sender_email}) поделился с вами документом.\n"
            f"Ознакомиться с ним можно по ссылке: {link}\n\n"
            f"EDMS GQ Group\n"
        )

        for recipient in mail_to:
            mail_service(
                mail_to=recipient,
                subject=subject,
                content=body,
                file_path=None
            )

    async def confirm_access(self, user: TokenData, url_id: str) -> bool:
        """
        Check whether the logged-in user is allowed to follow the share link.
        """
        stmt = select(SharedDocument).where(SharedDocument.url_id == url_id)
        result = await self.session.execute(stmt)
        record = result.scalar_one_or_none()
        if not record:
            raise http_404(msg="Ссылка для доступа недействительна или срок ее действия истек.")

        user_email = await self.get_user_mail(user)
        allowed = (
            record.owner_id == user.id
            or user_email in record.share_to
            or user.username in record.share_to
        )
        return allowed

    async def share_document(
        self,
        filename: str,
        share_request: SharingRequest,
        notify: bool,
        owner: TokenData,
        notify_repo: NotifyRepo,
        auth_repo: AuthRepository,
    ) -> None:
        """
        Email the actual file as an attachment, then optionally
        record a notification via NotifyRepo.
        """
        # 1) Resolve the full path on disk
        path: Path = await get_file_path(filename)

        # 2) Stream it into a NamedTemporaryFile so mail_service can attach it
        suffix = path.suffix
        with tempfile.NamedTemporaryFile(delete=True, suffix=suffix) as tmp:
            tmp.write(path.read_bytes())
            tmp.flush()

            user_email = await self.get_user_mail(owner)
            subject = f"{owner.username} поделился документом с вами"
            for recipient in share_request.share_to:
                body = (
                    f"Здравствуйте {recipient},\n\n"
                    f"{owner.username} ({user_email}) поделился документом с вами\n\n"
                    
                )
                mail_service(
                    mail_to=recipient,
                    subject=subject,
                    content=body,
                    file_path=tmp.name
                )

        # 3) Optionally record a notification entry
        if notify:
            await notify_repo.notify(
                user=owner,
                receivers=share_request.share_to,
                filename=filename,
                auth_repo=auth_repo
            )
1