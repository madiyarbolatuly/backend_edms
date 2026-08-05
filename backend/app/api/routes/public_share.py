"""
Public, token-based access to a single shared document or folder.

No authentication: whoever holds the link may read the target and everything
beneath it — and nothing else. Every endpoint runs the same two checks:

  1. the token resolves to a live link (exists, not revoked, not expired);
  2. the requested document lies inside that link's subtree.

Without (2), swapping the id in the URL would expose the whole library.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.database import get_async_session
from app.core.config import settings
from app.db.tables.base_class import DocStatus
from app.db.tables.documents.documents import Document
from app.db.tables.documents.share_link import ShareLink

from pathlib import Path

router = APIRouter(tags=["Public Share"])


async def resolve_share(token: str, session: AsyncSession) -> tuple[ShareLink, Document]:
    """Resolve a token to its link and target, or fail with a precise status."""
    link = (
        await session.execute(select(ShareLink).where(ShareLink.token == token))
    ).scalar_one_or_none()

    if link is None:
        raise HTTPException(status_code=404, detail="Ссылка не найдена")

    if link.revoked_at is not None:
        raise HTTPException(status_code=410, detail="Ссылка отозвана")

    if link.expires_at is not None and link.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=410, detail="Срок действия ссылки истёк")

    target = (
        await session.execute(
            select(Document)
            .where(Document.id == link.document_id)
            .where(Document.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    if target is None:
        raise HTTPException(status_code=404, detail="Документ больше не доступен")

    return link, target


def _is_within(doc: Document, root: Document) -> bool:
    """True when `doc` is the shared target itself or lives beneath it."""
    if doc.id == root.id:
        return True
    root_path = (root.file_path or "").rstrip("/")
    doc_path = doc.file_path or ""
    return bool(root_path) and doc_path.startswith(f"{root_path}/")


def _serialize(doc: Document) -> Dict[str, Any]:
    return {
        "id": doc.id,
        "name": doc.name,
        "file_type": doc.file_type,
        "size": doc.size,
        "created_at": doc.created_at,
        "parent_id": doc.parent_id,
    }


async def _folder_size(doc: Document, session: AsyncSession) -> Optional[int]:
    if doc.file_type != "folder":
        return doc.size
    from sqlalchemy import func

    prefix = (doc.file_path or "").rstrip("/")
    if not prefix:
        return None
    total = (
        await session.execute(
            select(func.coalesce(func.sum(Document.size), 0))
            .where(Document.tenant_id == doc.tenant_id)
            .where(Document.department_id == doc.department_id)
            .where(Document.deleted_at.is_(None))
            .where(Document.file_type != "folder")
            .where(Document.file_path.like(f"{prefix}/%"))
        )
    ).scalar_one()
    return int(total or 0)


@router.get("/share/{token}", status_code=status.HTTP_200_OK)
async def get_shared_target(
    token: str,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, Any]:
    """What the link points at, plus who shared it and until when."""
    link, target = await resolve_share(token, session)

    payload = _serialize(target)
    payload["size"] = await _folder_size(target, session)

    return {
        "document": payload,
        "expires_at": link.expires_at,
        "shared_at": link.created_at,
    }


@router.get("/share/{token}/children", status_code=status.HTTP_200_OK)
async def list_shared_children(
    token: str,
    parent_id: Optional[int] = None,
    session: AsyncSession = Depends(get_async_session),
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Children of a folder inside the shared subtree.

    `parent_id` defaults to the shared target; anything else must still be
    inside it.
    """
    _, root = await resolve_share(token, session)

    if parent_id is None:
        parent = root
    else:
        parent = (
            await session.execute(
                select(Document)
                .where(Document.id == parent_id)
                .where(Document.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        if parent is None:
            raise HTTPException(status_code=404, detail="Папка не найдена")
        if not _is_within(parent, root):
            raise HTTPException(status_code=403, detail="Вне области доступа ссылки")

    if parent.file_type != "folder":
        return {"documents": []}

    rows = (
        await session.execute(
            select(Document)
            .where(Document.parent_id == parent.id)
            .where(Document.deleted_at.is_(None))
            .where(Document.status != DocStatus.deleted)
            .order_by(Document.file_type.desc(), Document.name)
        )
    ).scalars().all()

    items = []
    for row in rows:
        entry = _serialize(row)
        entry["size"] = await _folder_size(row, session)
        items.append(entry)

    return {"documents": items}


@router.get("/share/{token}/download/{doc_id}")
async def download_shared_file(
    token: str,
    doc_id: int,
    session: AsyncSession = Depends(get_async_session),
) -> FileResponse:
    """Stream a file from inside the shared subtree."""
    _, root = await resolve_share(token, session)

    doc = (
        await session.execute(
            select(Document)
            .where(Document.id == doc_id)
            .where(Document.deleted_at.is_(None))
        )
    ).scalar_one_or_none()

    if doc is None:
        raise HTTPException(status_code=404, detail="Файл не найден")
    if not _is_within(doc, root):
        raise HTTPException(status_code=403, detail="Вне области доступа ссылки")
    if doc.file_type == "folder":
        raise HTTPException(status_code=400, detail="Нельзя скачать папку")

    abs_path = Path(settings.upload_dir) / (doc.file_path or "")
    if not abs_path.is_file():
        raise HTTPException(status_code=404, detail="Файл отсутствует на диске")

    return FileResponse(
        path=str(abs_path),
        filename=doc.name,
        media_type="application/octet-stream",
    )
