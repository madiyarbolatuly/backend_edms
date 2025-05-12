from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session
from services.documents import upload_document
from schemas.documents import DocumentUploadResponse
from utils.session import get_db  # assuming session setup
from fastapi import status

documentsRouter = APIRouter(prefix="/documents", tags=["Documents"])


@documentsRouter .post("/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Form(...),
    department_id: int = Form(...),
    title: str = Form(...),
    key: str = Form(...),
    value: str = Form(...),
    db: Session = Depends(get_db)
):
    return await upload_document(file, user_id, department_id, title, key, value, db)
