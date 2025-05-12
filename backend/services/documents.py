from fastapi import UploadFile
from pathlib import Path
from sqlalchemy.orm import Session
from models.documents import Document, DocumentStatus
from models.document_version import DocumentVersion
from database import SessionLocal
from datetime import datetime
import uuid
from app.api.dependencies.repositories import save_upload_file

UPLOAD_DIR = Path("uploaded_docs")
UPLOAD_DIR.mkdir(exist_ok=True)

async def upload_document(file: UploadFile, user_id: int, department_id: int, title: str, key: str, value: str, db: Session):
    unique_filename = await save_upload_file(file)

    document_number = uuid.uuid4().hex[:10]

    new_doc = Document(
        user_id=user_id,
        department_id=department_id,
        document_number=document_number,
        title=title,
        status=DocumentStatus.draft,
        media_path=str(UPLOAD_DIR / unique_filename),
        key=key,
        value=value,
        created_at=datetime.utcnow()
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

    new_version = DocumentVersion(
        document_id=new_doc.id,
        version_number=1,
        path=str(UPLOAD_DIR / unique_filename),
        created_at=datetime.utcnow()
    )
    db.add(new_version)
    db.commit()
    db.refresh(new_version)

    return {
        "message": "Upload successful",
        "document_id": new_doc.id,
        "version_id": new_version.id
    }
