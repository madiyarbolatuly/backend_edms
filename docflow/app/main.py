from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.openapi.utils import get_openapi
from contextlib import asynccontextmanager
import pathlib

from app.api.router import router
from app.core.config import settings
from app.db.models import check_tables

@asynccontextmanager
async def lifespan(app: FastAPI):
    await check_tables()
    yield

app = FastAPI(
    title=settings.title,
    version=settings.version,
    description=settings.description,
    docs_url=settings.docs_url,
    lifespan=lifespan,
)

# 1) CORS (for React dev on 3000/5173/8080)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://localhost:8080", "http://localhost:8081"],
    allow_methods=["*"],
    allow_headers=["*"],
)  # :contentReference[oaicite:5]{index=5}

# 2) Mount uploads folder BEFORE React SPA
uploads_path = pathlib.Path(__file__).parent.parent / "uploads"
app.mount(
    "/files",
    StaticFiles(directory=str(uploads_path), html=False),
    name="files",
)  # :contentReference[oaicite:6]{index=6}

# 3) Include your API routers
app.include_router(router=router, prefix=settings.api_prefix)

# 4) Mount React build as catch-all
frontend_build = pathlib.Path(__file__).parent / "frontend" / "dist"
if frontend_build.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_build), html=True),
        name="frontend",
    )  # :contentReference[oaicite:7]{index=7}

# 5) Favicon and root for OpenAPI
FAVICON_PATH = "favicon.ico"
@app.get(FAVICON_PATH, include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON_PATH)
