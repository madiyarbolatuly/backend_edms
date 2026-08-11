import secrets
from datetime import datetime, timezone
from typing import Union, Dict, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository
from app.core.config import settings
from app.core.exceptions import http_404
from app.core.utils import default_share_expiry
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.db.repositories.documents.document_sharing import SharedDocumentRepository
from app.schemas.auth.bands import TokenData
from app.schemas.documents.document_sharing import (
    SharingRequest,
    SharedDocumentListResponse,
    SharedDocumentRead,
    SharedDocumentUpdate,
)
from app.api.dependencies.mail_service import mail_service
# 2.5) resolve recipients
from app.db.tables.auth.auth import User
from app.db.repositories.auth.auth import AuthRepository
from app.db.tables.documents.share_link import ShareLink
from app.schemas.base import BaseSchema

from app.db.models import logger

router = APIRouter(tags=["Document Sharing"])


class ShareLinkCreate(BaseSchema):
    expires_at: Optional[datetime] = None


@router.post("/link/{document_id}", status_code=status.HTTP_201_CREATED, name="create_share_link")
async def create_share_link(
    document_id: int,
    body: ShareLinkCreate | None = None,
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Create ONE public link for a document or folder.

    Unlike /share-link/... (which records a per-document grant for a registered
    user), this mints a single token for the whole object; the recipient needs
    no account and sees only this object and what is inside it.
    """
    session = metadata_repository.session

    item = await metadata_repository.get_by_id_visible(document_id, user)
    if item is None:
        raise http_404(msg=f"Документ с id={document_id} не найден")

    link = ShareLink(
        token=secrets.token_urlsafe(32),
        document_id=item.id,
        created_by=user.id,
        # A link with no chosen date expires after `settings.share_expiry_days`.
        # It used to be stored as NULL, which this table reads as "never" — so
        # every public link ever created is still live.
        expires_at=(body.expires_at if body and body.expires_at else default_share_expiry()),
    )
    session.add(link)
    await session.commit()

    return {
        "token": link.token,
        "url": f"{settings.frontend_url}/s/{link.token}",
        "name": item.name,
    }


@router.delete("/link/{token}", status_code=status.HTTP_200_OK, name="revoke_share_link")
async def revoke_share_link(
    token: str,
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, str]:
    """Revoke a link. Kept as a row so the page can say "revoked", not "404"."""
    session = metadata_repository.session
    link = (
        await session.execute(select(ShareLink).where(ShareLink.token == token))
    ).scalar_one_or_none()

    if link is None:
        raise http_404(msg="Ссылка не найдена")
    if link.created_by != user.id and user.role != "admin":
        raise HTTPException(403, "Можно отозвать только свою ссылку")

    link.revoked_at = datetime.now(timezone.utc)
    await session.commit()
    return {"status": "revoked"}

@router.post(
    "/share-link/id/{file_id}",
    status_code=status.HTTP_200_OK,
    name="share_document_link_by_id"
)
async def share_link_document_by_id(
    file_id: int,
    share_request: SharingRequest,
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    share_repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Шаринг документа по его числовому ID.
    """
    users_repo = AuthRepository(metadata_repository.session)

    # 1) ищем документ по ID
    try:
        item = await metadata_repository.get_by_id_visible(file_id, user)
    except Exception:
        raise http_404(msg=f"Документ с id={file_id} не найден")

    # 2) собираем id всех документов (если папка → всё её содержимое)
    #    NB: Document has no `is_folder` column — folders are file_type == "folder".
    if item.file_type == "folder":
        descendants = await metadata_repository._list_descendants_raw(item)
        doc_ids = [item.id] + [d.id for d in descendants]
    else:
        doc_ids = [item.id]

    # 3) сохраняем в shared_documents
    # Every recipient is resolved before anything is written. Interleaved, an
    # unknown recipient part-way down the list aborted the request with the
    # earlier recipients already shared — and `create_share_records` committed
    # per call, so there was nothing to roll back.
    recipients = []
    for recipient_key in share_request.share_to or []:
        recipient = await users_repo.get_by_email_or_username(recipient_key)
        if not recipient:
            raise HTTPException(422, f"User {recipient_key} not found")
        recipients.append(recipient)

    for recipient in recipients:
        await share_repo.create_share_records(
            owner_id=user.id,
            doc_ids=doc_ids,
            shared_with_id=recipient.id,
            expires_at=share_request.expires_at,
        )

    # 4) уведомляем по email
    shared_url = f"{settings.frontend_url}/shared"

    if share_request.share_to:
        for recipient in share_request.share_to:
                try:
                    mail_service(
                        mail_to=recipient,
                        subject=f"Документ {item.name} был расшарен",
                        content=f"Вам предоставили доступ к документу {item.name}.\n\n"
                                f"Откройте по ссылке: {shared_url}"
                    )
                except Exception as e:
                    logger.warning(f"Mail not sent to {recipient}: {e}")


    return {"url": shared_url}


@router.post("/share-link/{document}", status_code=status.HTTP_200_OK, name="share_document_link")
async def share_link_document(
    document: Union[str, UUID],
    share_request: SharingRequest,
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    share_repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, str]:
    # 1) проверяем документ
    users_repo = AuthRepository(metadata_repository.session)

    item = await metadata_repository.get(document=document, owner=user)
    if item is None:
        raise http_404(msg=f"Документ «{document}» не найден")

    # 2) получаем id файлов (если папка → все внутри)
    doc_ids: list[int] = []
    if getattr(item, "file_type", None) == "folder":
        descendants = await metadata_repository._list_descendants_raw(item)
        doc_ids = [item.id] + [d.id for d in descendants]
    else:
        doc_ids = [item.id]

    # 3) сохраняем в shared_documents — сначала проверяем всех получателей,
    # потом пишем (см. share_link_document_by_id). `share_to` необязателен,
    # поэтому итерируем по `or []`: без этого пустое тело давало TypeError.
    recipients = []
    for recipient_key in share_request.share_to or []:
        recipient = await users_repo.get_by_email_or_username(recipient_key)
        if not recipient:
            raise HTTPException(422, f"User {recipient_key} not found")
        recipients.append(recipient)

    for recipient in recipients:
        await share_repo.create_share_records(
            owner_id=user.id,
            doc_ids=doc_ids,
            shared_with_id=recipient.id,
            expires_at=share_request.expires_at,
        )
    # 4) если есть получатели → разослать письмо
    shared_url = f"{settings.frontend_url}/shared"

    if share_request.share_to:
        for recipient in share_request.share_to:
            try:
                mail_service(
                    mail_to=recipient,
                    subject=f"Документ {item.name} был расшарен",
                    content=f"Вам предоставили доступ к документу {item.name}.\n\n"
                            f"Откройте по ссылке: {shared_url}"
                )
            except Exception as e:
                logger.warning(f"Mail not sent to {recipient}: {e}")

    return {"url": shared_url}

@router.get("/shared-by-me", status_code=status.HTTP_200_OK)
async def shared_by_me(
    repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
) -> SharedDocumentListResponse:
    """
    Вернёт список документов, расшаренных текущим пользователем.
    """
    rows = await repo.list_shared_by_user_rich(user.id)
    items: list[SharedDocumentRead] = []
    for share, shared_with_username, shared_with_email, file_path in rows:
        items.append(
            SharedDocumentRead(
                id=share.id,
                token=share.token,
                document_id=share.document_id,
                filename=share.filename,
                file_path=file_path,
                expires_at=share.expires_at,
                created_at=share.created_at,
                shared_by=share.shared_by,
                shared_with=share.shared_with,
                shared_with_name=shared_with_username or shared_with_email,
            )
        )
    return {"items": items}


@router.get("/shared-with-me", status_code=status.HTTP_200_OK)
async def shared_with_me(
    repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
) -> SharedDocumentListResponse:
    """
    Вернёт список документов, расшаренных другими для текущего пользователя.
    """
    rows = await repo.list_shared_with_user_rich(user.id)
    items: list[SharedDocumentRead] = []
    for share, shared_by_username, shared_by_email, file_path in rows:
        items.append(
            SharedDocumentRead(
                id=share.id,
                token=share.token,
                document_id=share.document_id,
                filename=share.filename,
                file_path=file_path,
                expires_at=share.expires_at,
                created_at=share.created_at,
                shared_by=share.shared_by,
                shared_by_name=shared_by_username or shared_by_email,
                shared_with=share.shared_with,
            )
        )
    return {"items": items}


@router.patch("/share/{share_id}", status_code=status.HTTP_200_OK)
async def update_share(
    share_id: int,
    payload: SharedDocumentUpdate,
    repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
):
    updated = await repo.update_share(
        share_id=share_id,
        actor_id=user.id,
        filename=payload.filename,
        expires_at=payload.expires_at,
    )
    return {
        "id": updated.id,
        "token": updated.token,
        "document_id": updated.document_id,
        "filename": updated.filename,
        "expires_at": updated.expires_at,
        "created_at": updated.created_at,
        "shared_by": updated.shared_by,
        "shared_with": updated.shared_with,
    }


@router.delete("/share/{share_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_share(
    share_id: int,
    repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
):
    await repo.delete_share(share_id=share_id, actor_id=user.id)
    return None
