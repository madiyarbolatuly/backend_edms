# ✨ TODO 

Following features are to be added and open for contributions:

- 🟨 Document Interactions - Adding Comments and Tags
- 🟨 Import documents from unread emails
- 🟨 Video Preview
- 🟨 Adding custom metadata fields to document
- 🟨 2-factor authentication
- 🟨 Storage quota per user? (Maybe to enable limit storage per user)
- 🟨 Bulk file importer
- ⭕ Group Share : Share a document to a group of users Needs: Group creation
- ⭕ Shared file history: History of all the shared files
- Linked list Stacks Pop psuh copy initialize destructor
Queues also
Deque Doubly linked list
INsert after insertbefore
remove

INSERT INTO documents (
    tenant_id,
    department_id,
    owner_id,
    file_type,
    document_number,
    title,
    name,
    status,
    file_path,
    is_archived,
    is_favourited,
    created_at
)
VALUES (
    1,
    1,
    '01K063DE332RJC7VXXRW0VHNHX',
    'application/pdf',
    'DOC-001',
    'tmp',
    'tmp.pdf',
    'draft',
    'tmp/tmp.pdf',
    FALSE,
    FALSE,
    now()
);
