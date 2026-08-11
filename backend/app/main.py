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
app.include_router(onlyoffice_router)


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
