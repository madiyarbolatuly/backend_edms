from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
import pathlib
from app.api.routes.onlyoffice import router as onlyoffice_router  # import ONLYOFFICE router
import os 
from app.api.router import router
from app.core.config import settings
from app.db.models import check_tables
from app.api.routes import auth, documents, folders, sharing, notifications, documents
from app.api.dependencies.auth_utils import get_current_user
from app.schemas.auth.bands import TokenData


@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_tables()
    yield

app = FastAPI(
    title=settings.title,
    version=settings.version,
    description=settings.description,
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True},
    docs_url=settings.docs_url,        # например "/docs"
    redoc_url=settings.redoc_url,      # например None или "/redoc"
    openapi_url=settings.openapi_url,  # например "/openapi.json"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


uploads_path = pathlib.Path(settings.upload_dir)  
app.mount(
    "/files",
    StaticFiles(directory=str(uploads_path), html=False),
    name="files",
)  # :contentReference[oaicite:6]{index=6}

app.include_router(router, prefix=settings.api_prefix)
# Same routes once more under /api. The built SPA calls `/api/v2/...` (see
# src/config/api.ts) because in dev the vite proxy strips the `/api` prefix;
# when the build is served straight from here there is no proxy to strip it,
# so the prefix has to exist on the API side. Kept out of the schema so /docs
# does not list every endpoint twice.
app.include_router(router, prefix=f"/api{settings.api_prefix}", include_in_schema=False)
app.include_router(onlyoffice_router)
app.include_router(onlyoffice_router, prefix="/api", include_in_schema=False)


# Served from this package, not the working directory. The path also needs its
# leading slash — request paths always start with one, so "favicon.ico" could
# never match — and the route has to be registered *before* the frontend mount
# below, because a mount at "/" matches everything that reaches it.
FAVICON_PATH = pathlib.Path(__file__).parent / "favicon.ico"


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    if not FAVICON_PATH.exists():
        raise HTTPException(status_code=404, detail="No favicon")
    return FileResponse(FAVICON_PATH)


class SPAStaticFiles(StaticFiles):
    """
    StaticFiles that falls back to index.html instead of 404ing.

    The SPA routes client-side (react-router), so /documents/42 exists only in
    the browser — as a request it hits this mount and matches no file. Plain
    StaticFiles answers 404, which breaks every deep link and every F5 on a
    page that is not "/". API paths are unaffected: their routes are
    registered before this mount and never reach it.
    """

    async def get_response(self, path: str, scope):
        response = await super().get_response(path, scope)
        if response.status_code == 404:
            return await super().get_response("index.html", scope)
        return response


def mount_frontend(application: FastAPI, build_dir: pathlib.Path) -> bool:
    """
    Serve the built SPA at the root, if there is one.

    Kept as a function so it can be exercised by a test. This previously passed
    `title=` to `mount()`, whose signature is `(path, app, name)` — a TypeError
    raised at import, and only on a deployment that actually has a build, since
    the call sits behind an existence check. It could not be caught anywhere the
    frontend is served by something else.
    """
    if not build_dir.exists():
        return False
    application.mount(
        "/",
        StaticFiles(directory=str(build_dir), html=True),
        name="frontend",
    )
    return True


mount_frontend(app, pathlib.Path(__file__).parent / "frontend" / "dist")
