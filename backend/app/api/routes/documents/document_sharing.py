from typing import Union, Dict
from uuid import UUID
from fastapi import APIRouter, Depends, status, HTTPException

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository
from app.core.config import settings
from app.core.exceptions import http_404
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

from app.db.models import logger

router = APIRouter(tags=["Document Sharing"])

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

    # 2) собираем id всех документов (если папка → всё содержимое)
    if getattr(item, "is_folder", False):
        descendants = await metadata_repository.list_documents_in_folder(
            item.id, recursive=True
        )
        doc_ids = [d.id for d in descendants]
    else:
        doc_ids = [item.id]

    # 3) сохраняем в shared_documents
    for recipient_key in share_request.share_to or []:
        recipient = await users_repo.get_by_email_or_username(recipient_key)
        if not recipient:
            raise HTTPException(422, f"User {recipient_key} not found")

        await share_repo.create_share_records(
            owner_id=user.id,
            doc_ids=doc_ids,
            shared_with_id=recipient.id,
            expires_at=share_request.expires_at,
        )

    # 4) уведомляем по email
    frontend_base = getattr(settings, "frontend_url", "http://77.245.107.136:8080")
    shared_url = f"{frontend_base}/shared"

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
    if getattr(item, "is_folder", False):
        descendants = await metadata_repository.list_documents_in_folder(item.id, recursive=True)
        doc_ids = [d.id for d in descendants]
    else:
        doc_ids = [item.id]

    # 3) сохраняем в shared_documents
    for recipient_key in share_request.share_to:
        recipient = await users_repo.get_by_email_or_username(recipient_key)
        if not recipient:
            raise HTTPException(422, f"User {recipient_key} not found")

        # 3) save record for each recipient
        await share_repo.create_share_records(
            owner_id=user.id,
            doc_ids=doc_ids,
            shared_with_id=recipient.id,
            expires_at=share_request.expires_at,
        )
    # 4) если есть получатели → разослать письмо
    frontend_base = getattr(settings, "frontend_url", "http://77.245.107.136:8080")
    shared_url = f"{frontend_base}/shared"

    if share_request.share_to:
        for recipient in share_request.share_to:
            mail_service(
                mail_to=recipient,
                subject=f"Документ {item.name} был расшарен",
                content=f"Вам предоставили доступ к документу {item.name}.\n\n"
                        f"Откройте по ссылке: {shared_url}"
            )

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
