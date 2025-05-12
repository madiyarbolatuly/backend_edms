import os
from pathlib import Path
import ulid

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

async def get_db() -> AsyncSession:
    async with async_session() as session:
        yield session
        await session.commit()


# ─── 4) Generic repository injector ────────────────────────────────────────────

def get_repository(repo_cls):
    def _get_repo(session: AsyncSession = Depends(get_db)):
        return repo_cls(session)
    return _get_repo


# ─── 5) ULID generator ────────────────────────────────────────────────────────

def get_ulid() -> str:
    return str(ulid.ULID())


# ─── 6) (Optional) Save an uploaded file to disk ───────────────────────────────

async def save_upload_file(upload_file: UploadFile) -> str:
    """
    Write the incoming UploadFile into UPLOAD_DIR and
    return the stored filename.
    """
    filename = f"{get_ulid()}_{upload_file.filename}"
    dest = UPLOAD_DIR / filename

    try:
        with dest.open("wb") as buffer:
            # Read in chunks to avoid large-memory spikes
            for chunk in iter(lambda: upload_file.file.read(1024 * 1024), b""):
                buffer.write(chunk)
    finally:
        upload_file.file.close()

    return filename


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
