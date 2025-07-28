# app/api/routes/documents/document_sharing.py
from uuid import UUID
from typing import Union, Dict

from fastapi import APIRouter, Depends, status
from fastapi.responses import RedirectResponse

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository
from app.core.config import settings
from app.core.exceptions import http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.db.repositories.documents.document_sharing import SharedDocumentRepository
from app.db.repositories.documents.notify import NotifyRepo
from app.schemas.auth.bands import TokenData
from app.schemas.documents.document_sharing import SharingRequest

router = APIRouter(tags=["Document Sharing"])


# ───────────────────────── share‑link ────────────────────────── #
@router.post(
    "/share-link/{document}",
    status_code=status.HTTP_200_OK,
    name="share_document_link",
)
async def share_link_document(
    document: Union[str, UUID],
    share_request: SharingRequest,
    repository: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    auth_repository: AuthRepository = Depends(get_repository(AuthRepository)),
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    notify_repository: NotifyRepo = Depends(get_repository(NotifyRepo)),
    user: TokenData = Depends(get_current_user),
) -> Dict[str, str]:
    """
    Создаёт (или переиспользует) персональные ссылки для `share_to`
    и рассылает письма / нотификации.
    """
    # 1) проверяем, что документ принадлежит пользователю
    doc = await metadata_repository.get(document=document, owner=user)
    if doc is None:
        raise http_404(msg=f"Документ «{document}» не найден")

    # 2) создаём / получаем ссылки
    share_data = await repository.get_shareable_link(
        owner=user,
        filename=doc.name,
        share_to=share_request.share_to,
        expires_at=share_request.expires_at,
    )
    links_for_people = share_data["links"]            # {recipient: url}

    # 3) рассылаем письма + нотификации
    for recipient, link in links_for_people.items():
        await repository.send_mail(user=user, mail_to=[recipient], link=link)
        await notify_repository.notify(
            user=user,
            receivers=[recipient],
            filename=doc.name,
            auth_repo=auth_repository,
        )

    personal_url = f"{settings.host_url}/uploads/{doc.name}"
    return {
        "personal_url": personal_url,
        "shareable_links": links_for_people,
        "expires_at": share_data["expires_at"],
    }


# ───────────────────────── redirect ──────────────────────────── #
@router.get("/doc/{token}", tags=["Document Sharing"])
async def redirect_to_share(
    token: str,
    repository: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    user: TokenData = Depends(get_current_user),
):
    """
    Проверяет права и перенаправляет на настоящий URL файла.
    """
    if not await repository.confirm_access(user=user, token=token):
        raise http_404(msg="Нет доступа к документу")

    redirect_url = await repository.get_redirect_url(token=token)
    return RedirectResponse(redirect_url)


# ───────────────────────── share‑document (отправка файла) ───── #
@router.post(
    "/share/{document}",
    status_code=status.HTTP_200_OK,
    name="share_document",
)
async def share_document(
    document: Union[str, UUID],
    share_request: SharingRequest,
    notify: bool = True,
    repository: SharedDocumentRepository = Depends(get_repository(SharedDocumentRepository)),
    metadata_repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
    notify_repo: NotifyRepo = Depends(get_repository(NotifyRepo)),
    auth_repo: AuthRepository = Depends(get_repository(AuthRepository)),
    user: TokenData = Depends(get_current_user),
) -> None:
    """
    Отсылает сам файл во вложении, опционально создаёт нотификации.
    """
    doc = await metadata_repository.get(document=document, owner=user)
    if doc is None:
        raise http_404(msg="Документ не найден")

    await repository.share_document(
        filename=doc.name,
        share_request=share_request,
        notify=notify,
        owner=user,
        notify_repo=notify_repo,
        auth_repo=auth_repo,
    )
