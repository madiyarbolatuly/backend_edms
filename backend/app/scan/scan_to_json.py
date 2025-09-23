import os
import hashlib
import json
import uuid
from datetime import datetime, timezone

ROOT_SCAN = "/home/fanatik/madiyar/final/docedms/backend/uploads/1/1/ПГУ"
ROOT_NAME = os.path.basename(ROOT_SCAN.rstrip("/"))

TENANT_ID = 1
DEPARTMENT_ID = 1
OWNER_ID = "c17ba46f-b4b0-473c-ac93-cb10cfed0f7e"  # твой реальный user_id

def get_file_hash(filepath):
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            h.update(chunk)
    return h.hexdigest()

def scan():
    docs = []
    now = datetime.now(timezone.utc).isoformat()

    # Root folder
    root_doc = {
        "tenant_id": TENANT_ID,
        "department_id": DEPARTMENT_ID,
        "owner_id": OWNER_ID,
        "file_type": "folder",
        "document_number": str(uuid.uuid4()),
        "title": ROOT_NAME,
        "name": ROOT_NAME,
        "status": "private",
        "file_path": ROOT_SCAN,
        "is_archived": False,
        "is_favourited": False,
        "file_hash": None,
        "created_at": now,
        "deleted_at": None,
        "parent_id": None
    }
    docs.append(root_doc)

    # Walk files
    for dirpath, dirnames, filenames in os.walk(ROOT_SCAN):
        rel_path = os.path.relpath(dirpath, ROOT_SCAN)
        parent_path = ROOT_SCAN if rel_path == "." else os.path.join(ROOT_SCAN, rel_path)

        # Folders
        for d in dirnames:
            docs.append({
                "tenant_id": TENANT_ID,
                "department_id": DEPARTMENT_ID,
                "owner_id": OWNER_ID,
                "file_type": "folder",
                "document_number": str(uuid.uuid4()),
                "title": d,
                "name": d,
                "status": "private",
                "file_path": os.path.join(parent_path, d),
                "is_archived": False,
                "is_favourited": False,
                "file_hash": None,
                "created_at": now,
                "deleted_at": None,
                "parent_id": None  # можно позже заменить на id родителя
            })

        # Files
        for f in filenames:
            abs_path = os.path.join(dirpath, f)
            docs.append({
                "tenant_id": TENANT_ID,
                "department_id": DEPARTMENT_ID,
                "owner_id": OWNER_ID,
                "file_type": "file",
                "document_number": str(uuid.uuid4()),
                "title": f,
                "name": f,
                "status": "draft",
                "file_path": abs_path,
                "is_archived": False,
                "is_favourited": False,
                "file_hash": get_file_hash(abs_path),
                "created_at": now,
                "deleted_at": None,
                "parent_id": None
            })

    return docs


if __name__ == "__main__":
    docs = scan()
    with open("documents.json", "w", encoding="utf-8") as f:
        json.dump(docs, f, ensure_ascii=False, indent=2)
    print("✅ Saved metadata to documents.json")
