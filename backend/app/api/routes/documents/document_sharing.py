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
from app.schemas.documents.document_sharing import SharingRequest
from app.api.dependencies.mail_service import mail_service
# 2.5) resolve recipients
from app.db.tables.auth.auth import User
from app.db.repositories.auth.auth import AuthRepository


router = APIRouter(tags=["Document Sharing"])


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
    frontend_base = getattr(settings, "frontend_url", "http://localhost:8080")
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
):
    """
    Вернёт список документов, расшаренных текущим пользователем.
    """
    return await repo.list_shared_by_user(user.id)


@router.get("/shared-with-me", status_code=status.HTTP_200_OK)
async def shared_with_me(
    repo: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
):
    """
    Вернёт список документов, расшаренных другими для текущего пользователя.
    """
    return await repo.list_shared_with_user(user.id)
