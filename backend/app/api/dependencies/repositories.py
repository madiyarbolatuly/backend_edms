import os
from pathlib import Path
from app.core.utils import get_ulid

from fastapi import Depends, UploadFile, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import async_session


# ─── 1) Make sure the upload directory exists ──────────────────────────────────

UPLOAD_DIR = Path(settings.upload_dir)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


# ─── 2) TempFileResponse: auto-delete after use ───────────────────────────────

class TempFileResponse(FileResponse):
    def __init__(self, path: Path, *args, **kwargs):
        super().__init__(path, *args, **kwargs)
        self._path = path

    def __del__(self):
        if self._path.exists():
            self._path.unlink()


# ─── 3) DB session dependency ─────────────────────────────────────────────────

from typing import AsyncGenerator

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session
        await session.commit()


# ─── 4) Generic repository injector ────────────────────────────────────────────

def get_repository(repo_cls):
    def _get_repo(session: AsyncSession = Depends(get_db)):
        return repo_cls(session)
    return _get_repo


# ─── 6) (Optional) Save an uploaded file to disk ───────────────────────────────

async def save_upload_file(
        upload_file: UploadFile,
        tenant_id: int,
        department_id: int,
        sub_folder: str | None = None,
    ) -> str:
    """
    Write the incoming UploadFile into UPLOAD_DIR and
    return the stored filename.
    """
    filename = f"{upload_file.filename}_{get_ulid()}"
    dest_dir: Path = UPLOAD_DIR / str(tenant_id) / str(department_id)
    if sub_folder:
        dest_dir = dest_dir / sub_folder
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / filename

    try:
        with dest.open("wb") as buffer:
            # Read in chunks to avoid large-memory spikes
            for chunk in iter(lambda: upload_file.file.read(1024 * 1024), b""):
                buffer.write(chunk)
    finally:
        upload_file.file.close()

    return str(dest.relative_to(UPLOAD_DIR))


# ─── 7) Resolve a stored filename to its Path ─────────────────────────────────

async def get_file_path(filename: str) -> Path:
    """
    Return the Path to a file under UPLOAD_DIR, or
    raise a 404 if it doesn’t exist.
    """
    full_path = UPLOAD_DIR / filename
    if not full_path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    return full_path
