# app/integrations/onlyoffice.py
import os, time, hashlib, jwt
from typing import Literal

ONLYOFFICE_JWT_SECRET = os.getenv("ONLYOFFICE_JWT_SECRET", "supersecret_please_change")
DOCUMENT_SERVER_PUBLIC = os.getenv("DOCUMENT_SERVER_PUBLIC", "http://localhost:8085")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")
UPLOAD_ROOT = os.getenv("UPLOAD_ROOT", "/var/docedms/uploads")

DOC_TYPE_BY_EXT = {
    "docx": "word",
    "xlsx": "cell",
    "pptx": "slide",
}

def build_doc_key(doc_id: str, version_hint: int = 1) -> str:
    raw = f"{doc_id}:{version_hint}:{int(time.time() // (60*10))}"  # rotates every 10 min
    return hashlib.sha256(raw.encode()).hexdigest()

def sign_token(payload: dict) -> str:
    return jwt.encode(payload, ONLYOFFICE_JWT_SECRET, algorithm="HS256")
