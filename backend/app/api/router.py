# app/api/router.py

from fastapi import APIRouter
from app.api.routes.documents.folders import router as folders_router
from app.api.routes.documents.documents_metadata import router as metadata_router
from app.api.routes.documents.documents import router as documents_router
from app.api.routes.documents.document_organization import router as filter_router
from app.api.routes.documents.document_sharing import router as sharing_router
from app.api.routes.documents.notify import router as notify_router
from app.api.routes.auth.auth import router as auth_router
from app.api.routes.onlyoffice import router as onlyoffice_router

router = APIRouter()

# единый стиль: каждый подроутер получает свой «листовой» префикс
router.include_router(auth_router,        prefix="/u")
router.include_router(documents_router,   prefix="")              # т.к. внутри уже есть свои пути
router.include_router(notify_router,      prefix="/notifications")
router.include_router(metadata_router,    prefix="/metadata")
router.include_router(filter_router,      prefix="/filter")
router.include_router(sharing_router,     prefix="/sharing")
router.include_router(folders_router,     prefix="/folders")      # ← БЕЗ /api/v2
router.include_router(onlyoffice_router,  prefix="/office")       # ← перенесли ONLYOFFICE под /v2
