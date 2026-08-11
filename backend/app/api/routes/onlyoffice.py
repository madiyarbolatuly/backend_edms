# app/routers/onlyoffice.py
import logging
from typing import Literal, Optional
from urllib.parse import quote

import httpx
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from pydantic import BaseModel, Field

from app.api.dependencies.auth_utils import get_current_user
from app.api.dependencies.repositories import get_repository
from app.core.config import settings
from app.db.repositories.documents.documents_metadata import MetadataRepository
from app.integrations.onlyoffice import (
    DOC_TYPE_BY_EXT, DOCUMENT_SERVER_PUBLIC, BACKEND_PUBLIC_URL,
    OnlyOfficeNotConfigured, build_doc_key, is_document_server_url,
    sign_token, verify_token,
)
from app.schemas.auth.bands import TokenData
from app.services.versioning import resolve_within_storage, save_new_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/office", tags=["onlyoffice"])


# ---- Request model for /office/config
class OfficeConfigRequest(BaseModel):
    doc_id: str = Field(..., description="Your document ID")
    ext: Literal["docx","xlsx","pptx"]
    title: Optional[str] = Field(None, description="File name for display, e.g., 'Report.docx'")
    mode: Literal["edit","view"] = "edit"
    user_id: str
    user_name: str


def _not_configured() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            "Редактор недоступен: не задан ONLYOFFICE_JWT_SECRET. "
            "Значение должно совпадать с JWT_SECRET у Document Server."
        ),
    )


@router.post("/config")
async def get_onlyoffice_config(
    payload: OfficeConfigRequest,
    # Was unauthenticated, so anyone could mint a signed edit config for any
    # document id. The frontend already sends a bearer token.
    user: TokenData = Depends(get_current_user),
    repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    try:
        document_id = int(payload.doc_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="doc_id должен быть числом")

    # Confirm the caller may open this document, rather than trusting the id in
    # the body. Also gives us the real file name for the download URL.
    doc = await repository._get_scoped(document_id, user)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Документ {document_id} не найден")

    # Document Server fetches this itself, so it must be reachable from there.
    file_download_url = f"{BACKEND_PUBLIC_URL}/v2/file/{document_id}/download"

    ext_q = payload.ext
    title_q = quote(payload.title or doc.name or f"{document_id}.{payload.ext}")
    callback_url = (
        f"{BACKEND_PUBLIC_URL}/office/callback/{document_id}"
        f"?ext={ext_q}&title={title_q}"
    )

    doc_type = DOC_TYPE_BY_EXT[payload.ext]
    key = build_doc_key(str(document_id), version_hint=1)

    config = {
        "document": {
            "fileType": payload.ext,
            "key": key,
            "title": payload.title or doc.name or f"{document_id}.{payload.ext}",
            "url": file_download_url,
            "permissions": {
                "edit": payload.mode == "edit",
                "download": True,
                "print": True,
                "comment": True
            }
        },
        "documentType": doc_type,
        "editorConfig": {
            "mode": "edit" if payload.mode == "edit" else "view",
            "callbackUrl": callback_url,
            # Identify the actual caller, not whatever the body claimed.
            "user": {"id": str(user.id), "name": user.username},
            "customization": {"autosave": True}
        }
    }

    try:
        config["token"] = sign_token(config)
    except OnlyOfficeNotConfigured:
        raise _not_configured()

    return {
        "documentServerUrl": DOCUMENT_SERVER_PUBLIC,
        "config": config
    }


def _callback_token(request: Request, body: dict) -> Optional[str]:
    """Document Server sends the JWT in the Authorization header, the body, or both."""
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip()
    token = body.get("token")
    return token if isinstance(token, str) and token else None


@router.post("/callback/{doc_id}")
async def onlyoffice_callback(
    doc_id: str = Path(...),
    request: Request = None,
    ext: Literal["docx","xlsx","pptx"] = Query(...),
    title: Optional[str] = Query(None),
    repository: MetadataRepository = Depends(get_repository(MetadataRepository)),
):
    """
    Document Server's save callback.

    This had no authentication of any kind and never checked the JWT that
    Document Server signs it with, so anyone who could reach the endpoint could
    post `{"status": 2, "url": "..."}` and have the server fetch that URL — any
    URL — and write the response over a document. `doc_id` went straight into a
    filesystem path, so `../../` escaped the upload root as well.

    Now: the token is verified, the verified payload is what is trusted, the
    fetch is restricted to the configured Document Server, and the write path is
    resolved from the document row and checked for containment.
    """
    body = await request.json()

    token = _callback_token(request, body)
    if not token:
        raise HTTPException(status_code=401, detail="Missing callback token")

    try:
        claims = verify_token(token)
    except OnlyOfficeNotConfigured:
        raise _not_configured()
    except Exception:
        raise HTTPException(status_code=403, detail="Invalid callback token")

    # Document Server nests the callback body under "payload" in some versions.
    verified = claims.get("payload") if isinstance(claims.get("payload"), dict) else claims

    status = verified.get("status", body.get("status"))
    # 2 (Saved), 6/7 (Force Save variants) => fetch edited file
    if status not in (2, 6, 7):
        # Other statuses: acknowledge
        return {"error": 0}

    # From the *verified* payload — never the raw body.
    url = verified.get("url")
    if not url:
        return {"error": 1}

    if not is_document_server_url(url):
        logger.warning("onlyoffice callback: refused to fetch %s", url)
        raise HTTPException(status_code=400, detail="Callback URL is not allowed")

    try:
        document_id = int(doc_id)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="doc_id должен быть числом")

    doc = await repository.get_document_for_callback(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail=f"Документ {document_id} не найден")

    try:
        target = resolve_within_storage(doc.file_path)
    except ValueError:
        logger.warning("onlyoffice callback: path escapes storage for doc %s", document_id)
        raise HTTPException(status_code=400, detail="Invalid document path")

    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.get(url)
        if response.status_code != 200:
            return {"error": 1}
        content = response.content

    save_new_version(absolute_path=target, doc_id=document_id, content=content)
    await repository.record_saved_content(doc, size=len(content))

    return {"error": 0}
