import os
import hashlib
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.db.tables.documents.documents import Document
from app.db.tables.base_class import DocStatus

# Database configuration. Read from the environment like the rest of the app —
# this used to hardcode a production password in the clear.
DATABASE_URL = os.environ.get("DATABASE_URL") or settings.sync_database_url
engine = create_engine(DATABASE_URL, echo=True)  # echo=True = покажет SQL-запросы
SessionLocal = sessionmaker(bind=engine)
session = SessionLocal()

# Config
BASE_DIRECTORY = "/home/fanatik/madiyar/final/docedms/backend/uploads/Projects-2025/ПГУ-Туркестан"
TENANT_ID = 1
DEPARTMENT_ID = 1
OWNER_ID = "01K33DTSJ92FF4FRAKW0TRTWYE"

# Хранилище для связей папок
folder_docs = {}

# Счётчики
folders_added = 0
files_added = 0
folders_skipped = 0
files_skipped = 0

try:
    print(f"🚀 Starting import from: {BASE_DIRECTORY}")
    for current_dir, subdirs, files in os.walk(BASE_DIRECTORY):
        relative_dir_path = "" if current_dir == BASE_DIRECTORY else os.path.relpath(current_dir, BASE_DIRECTORY)

        # --- обрабатываем папки ---
        if relative_dir_path != "":
            folder_name = os.path.basename(current_dir)
            parent_relative_path = os.path.dirname(relative_dir_path) if relative_dir_path else ""
            parent_doc = folder_docs.get(parent_relative_path) if parent_relative_path not in ("", ".") else None

            folder_file_path = f"{parent_doc.file_path}/{folder_name}" if parent_doc else folder_name
            print(f"📁 Creating folder entry: {folder_file_path}")

            folder_doc = Document(
                tenant_id=TENANT_ID,
                department_id=DEPARTMENT_ID,
                owner_id=OWNER_ID,
                file_type="folder",
                title=folder_name,
                name=folder_name,
                status=DocStatus.draft,
                file_path=folder_file_path,
                file_hash=None,
                parent_id=parent_doc.id if parent_doc else None
            )
            session.add(folder_doc)
            try:
                session.flush()
                folder_docs[relative_dir_path] = folder_doc
                folders_added += 1
            except IntegrityError:
                session.rollback()
                print(f"⚠️ Skipped duplicate folder: {folder_file_path}")
                folders_skipped += 1

        # --- обрабатываем файлы ---
        for filename in files:
            file_path_full = os.path.join(current_dir, filename)
            file_rel_path = f"{relative_dir_path}/{filename}" if relative_dir_path else filename

            # считаем SHA256
            sha256 = hashlib.sha256()
            file_size = 0
            with open(file_path_full, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
                    file_size += len(chunk)
            file_hash_hex = sha256.hexdigest()

            parent_doc = folder_docs.get(relative_dir_path) if relative_dir_path != "" else None
            print(f"📄 Adding file: {file_rel_path} (size={file_size} bytes, sha256={file_hash_hex[:12]}...)")

            file_doc = Document(
                tenant_id=TENANT_ID,
                department_id=DEPARTMENT_ID,
                owner_id=OWNER_ID,
                file_type="file",
                title=filename,
                name=filename,
                status=DocStatus.draft,
                file_path=file_rel_path,
                file_hash=file_hash_hex,
                parent_id=parent_doc.id if parent_doc else None
            )
            session.add(file_doc)
            try:
                session.flush()
                files_added += 1
            except IntegrityError:
                session.rollback()
                print(f"⚠️ Skipped duplicate file: {file_rel_path}")
                files_skipped += 1

    print("💾 Committing changes...")
    session.commit()
    print("✅ Import completed successfully.")
    print(f"📊 Report: {folders_added} folders added, {files_added} files added, "
          f"{folders_skipped} folders skipped, {files_skipped} files skipped.")

except Exception as e:
    import traceback
    traceback.print_exc()
    session.rollback()
    print(f"❌ Error during import: {e}")

finally:
    session.close()
    print("🔒 Session closed.")
