import json

with open("documents.json", "r", encoding="utf-8") as f:
    docs = json.load(f)

with open("insert_documents.sql", "w", encoding="utf-8") as out:
    for d in docs:
        out.write(f"""
INSERT INTO documents (
    tenant_id, department_id, owner_id, file_type, document_number,
    title, name, status, file_path, is_archived, is_favourited,
    file_hash, created_at, deleted_at, parent_id
) VALUES (
    {d["tenant_id"]}, {d["department_id"]}, '{d["owner_id"]}',
    '{d["file_type"]}', '{d["document_number"]}',
    '{d["title"].replace("'", "''")}', '{d["name"].replace("'", "''")}',
    '{d["status"]}', '{d["file_path"].replace("'", "''")}',
    {'true' if d["is_archived"] else 'false'},
    {'true' if d["is_favourited"] else 'false'},
    {f"'{d['file_hash']}'" if d["file_hash"] else "NULL"},
    '{d["created_at"]}', NULL, NULL
);
""")
print("✅ Saved SQL insert script as insert_documents.sql")

