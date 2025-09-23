import os, hashlib, psycopg, uuid
import time
from datetime import datetime, timezone

# ── DB (дефолты из твоего примера; можно переопределять через ENV)
DB_NAME = os.environ.get("POSTGRES_DB", "docflow_db")
USER = os.environ.get("POSTGRES_USER", "postgres")
PASSWORD = os.environ.get("POSTGRES_PASSWORD", "GQgroup12")
HOST = os.environ.get("POSTGRES_HOST", "postgres")
PORT = os.environ.get("POSTGRES_PORT", "5432")

TENANT_ID = int(os.environ.get("TENANT_ID", "1"))
DEPARTMENT_ID = int(os.environ.get("DEPARTMENT_ID", "1"))
OWNER_ID = os.environ.get("OWNER_ID", "9c5589f4-57bf-425f-a94a-b41c5f30649")  # подставь свой точный

# ── Корень для сканирования (обязательно!)
ROOT_SCAN = os.environ.get("ROOT_SCAN", "/mnt//Projects-2025/ ")
# Имя, которое будет храниться в documents.file_path как префикс (можно задать полностью)
ROOT_PREFIX = os.environ.get("ROOT_PREFIX") or os.path.basename(ROOT_SCAN.rstrip("/"))

HASH_FILES = os.environ.get("HASH_FILES", "true").lower() == "true"

def get_file_hash(path):
    if not HASH_FILES:
        return None
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""): h.update(chunk)
    return h.hexdigest()

def insert_document(cur, file_type, title, name, status, file_path, parent_id, file_hash=None):
    cur.execute("""
        INSERT INTO documents(
          tenant_id, department_id, owner_id,
          file_type, document_number, title, name,
          status, file_path, is_archived, is_favourited,
          file_hash, created_at, parent_id
        ) VALUES (
          %s,%s,%s,%s,%s,%s,%s,%s,%s,false,false,%s,%s,%s
        ) RETURNING id;
    """, (
        TENANT_ID, DEPARTMENT_ID, OWNER_ID,
        file_type, str(uuid.uuid4()), title, name,
        status, file_path, file_hash, datetime.now(timezone.utc), parent_id
    ))
    return cur.fetchone()[0]

def process_directory(cur, parent_id, fs_path):
    for item in os.listdir(fs_path):
      
        if item.strip() == "ПГУ-Туркестан":
            print(f"⏭ Пропущена папка: {item}")
            continue

        abs_path = os.path.join(fs_path, item)
        rel_path = os.path.relpath(abs_path, ROOT_SCAN)

        db_path = f"1/1/{ROOT_PREFIX}/{rel_path}"

        if os.path.isdir(abs_path):
            folder_id = insert_document(
                cur, "folder", item, item, "private", db_path, parent_id
            )
            process_directory(cur, folder_id, abs_path)
        else:
            file_hash = get_file_hash(abs_path)
            insert_document(
                cur, "file", item, item, "draft", db_path, parent_id, file_hash
            )

def wait_for_postgres(retries=10, delay=3):
    for i in range(retries):
        try:
            conn = psycopg.connect(
                dbname=DB_NAME,
                user=USER,
                password=PASSWORD,
                host=HOST,
                port=PORT
            )
            conn.close()
            print("✅ Postgres is ready!")
            return
        except psycopg.OperationalError as e:
            print(f"⏳ Waiting for Postgres... ({i+1}/{retries}) {e}")
            time.sleep(delay)
    raise SystemExit("❌ Postgres is not ready after retries")

def main():
    if not os.path.isdir(ROOT_SCAN):
        raise SystemExit(f"ROOT_SCAN not found: {ROOT_SCAN}")

    wait_for_postgres()  # 👈 ждём пока БД станет доступной

    with psycopg.connect(
        dbname=DB_NAME, user=USER, password=PASSWORD, host=HOST, port=PORT
    ) as conn:
        with conn.cursor() as cur:
            root_id = insert_document(cur, "folder", ROOT_PREFIX, ROOT_PREFIX,
                                      "private", f"1/1/{ROOT_PREFIX}", None)
            process_directory(cur, root_id, ROOT_SCAN)
        conn.commit()

    print(f"✔ Indexed {ROOT_SCAN} as '{ROOT_PREFIX}'")

if __name__ == "__main__":
    main()
