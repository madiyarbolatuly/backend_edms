# app/routers/onlyoffice.py
from fastapi import APIRouter, HTTPException, Request, Query, Path
from pydantic import BaseModel, Field
from typing import Literal, Optional
from urllib.parse import quote
import httpx, os

from app.integrations.onlyoffice import (
    DOC_TYPE_BY_EXT, DOCUMENT_SERVER_PUBLIC, BACKEND_PUBLIC_URL,
    build_doc_key, sign_token
)
from app.services.versioning import save_new_version

router = APIRouter(prefix="/office", tags=["onlyoffice"])

# ---- Request model for /office/config
class OfficeConfigRequest(BaseModel):
    doc_id: str = Field(..., description="Your document ID")
    ext: Literal["docx","xlsx","pptx"]
    title: Optional[str] = Field(None, description="File name for display, e.g., 'Report.docx'")
    mode: Literal["edit","view"] = "edit"
    user_id: str
    user_name: str

@router.post("/config")
async def get_onlyoffice_config(payload: OfficeConfigRequest):
    # Build download URL.  // TODO: CHANGE ME if your download API differs
    # The URL must be reachable by ONLYOFFICE Document Server.
    file_download_url = f"{BACKEND_PUBLIC_URL}/api/files/{quote(payload.doc_id)}/download"

    # Pass ext & title back to callback via query to avoid DB lookups
    ext_q = payload.ext
    title_q = quote(payload.title or f"{payload.doc_id}.{payload.ext}")
    callback_url = f"{BACKEND_PUBLIC_URL}/office/callback/{quote(payload.doc_id)}?ext={ext_q}&title={title_q}"

    doc_type = DOC_TYPE_BY_EXT[payload.ext]
    key = build_doc_key(payload.doc_id, version_hint=1)

    config = {
        "document": {
            "fileType": payload.ext,
            "key": key,
            "title": payload.title or f"{payload.doc_id}.{payload.ext}",
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
            "user": {"id": payload.user_id, "name": payload.user_name},
            "customization": {"autosave": True}
        }
    }

    token = sign_token(config)
    # ONLYOFFICE accepts token embedded in config
    config["token"] = token

    return {
        "documentServerUrl": DOCUMENT_SERVER_PUBLIC,
        "config": config
    }

@router.post("/callback/{doc_id}")
async def onlyoffice_callback(
    doc_id: str = Path(...),
    request: Request = None,
    ext: Literal["docx","xlsx","pptx"] = Query(...),
    title: Optional[str] = Query(None)
):
   
    data = await request.json()
    status = data.get("status")
    # 2 (Saved), 6/7 (Force Save variants) => fetch edited file
    if status in (2, 6, 7):
        url = data.get("url")
        if not url:
            return {"error": 1}
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.get(url)
            if r.status_code != 200:
                return {"error": 1}
            content = r.content

        # Persist with lightweight versioning
        save_new_version(doc_id=doc_id, ext=ext, content=content)
        return {"error": 0}

    # Other statuses: acknowledge
    return {"error": 0}
