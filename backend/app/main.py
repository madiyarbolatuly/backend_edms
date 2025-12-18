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
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:8000",
        "http://77.245.107.136:8080",
        "http://192.168.8.121:8080",       
        ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


uploads_path = pathlib.Path(__file__).parent.parent / "uploads"
app.mount(
    "/files",
    StaticFiles(directory=str(uploads_path), html=False),
    name="files",
)  # :contentReference[oaicite:6]{index=6}

app.include_router(router, prefix=settings.api_prefix)
app.include_router(onlyoffice_router)



frontend_build = pathlib.Path(__file__).parent / "frontend" / "dist"
if frontend_build.exists():
    app.mount(
        "/",
        StaticFiles(directory=str(frontend_build), html=True),
        name="frontend",
        title=settings.title,
    )

FAVICON_PATH = "favicon.ico"
@app.get(FAVICON_PATH, include_in_schema=False)
async def favicon():
    return FileResponse(FAVICON_PATH)
