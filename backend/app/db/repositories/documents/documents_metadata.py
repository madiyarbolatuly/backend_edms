from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Union
from uuid import UUID
from app.db.tables.documents.versions import DocumentVersion    
from fastapi import HTTPException
from sqlalchemy import select, update, insert, delete
from sqlalchemy.engine import Row
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from app.core.exceptions import http_409, http_404
from app.db.repositories.auth.auth import AuthRepository
from app.db.tables.auth.auth import User
from app.db.tables.documents.documents import Document
from app.db.tables.base_class import DocStatus
from app.schemas.auth.bands import TokenData
from app.schemas.documents.bands import DocumentMetadataPatch
from app.schemas.documents.documents_metadata import (
    DocumentMetadataCreate,
    DocumentMetadataRead,
)
from app.db.base import BaseRepository
from pathlib import Path, PurePosixPath
import hashlib
from typing import List, Optional
from fastapi import UploadFile
from app.schemas.documents.documents_metadata import FolderCreate, FolderRead
from app.db.tables.documents.permissions import Permission, AccessLevel
from app.db.tables.documents.permissions import doc_user_access
# Everything that carries a FK to documents.id — a permanent delete has to clear
# these first, since the ORM-level cascade does not apply to Core DELETE.
from app.db.tables.documents.share_link import ShareLink
from app.db.tables.documents.shared import SharedDocument
from enum import Enum
from app.core.config import settings
from app.db.models import logger
from sqlalchemy.orm import aliased
from sqlalchemy import select, update, insert, delete, func, and_, or_
from pathlib import PurePosixPath, Path
import os, shutil
from app.api.dependencies.repositories import get_file_path
from pathlib import Path, PurePosixPath
import os, shutil
from fastapi import HTTPException
import logging
import os
import shutil
from pathlib import Path
import logging
logger = logging.getLogger(__name__)


UPLOADS_ROOT = Path("/home/madiyar/Desktop/docedms/backend/uploads") 
# helper: построить абсолютный путь БЕЗ проверки существования
def build_abs_path(storage_root: str, rel_path: str) -> Path:
    # rel_path всегда posix-путь
    return Path(storage_root) / rel_path

def with_prefix(user, rel: str | None) -> str:
    rel = (rel or "").strip("/")
    prefix = f"{user.tenant_id}/{user.department_id}"
    return f"{prefix}/{rel}" if rel else prefix

async def _join_posix(a: str | None, b: str | None) -> str:
        """
        Join 2 posix segments without duplicate slashes.
        If a is falsy, returns b. If b is falsy, returns a. 
        """
        a = (a or "").strip("/")
        b = (b or "").strip("/")
        if not a: 
            return b
        if not b:
            return a
        return f"{a}/{b}"

async def _get_base_parent(self, base_parent_id: int | None, user: TokenData) -> Document | None:
        if base_parent_id is None:
            return None
        q = (
            select(Document)
            .where(Document.id == base_parent_id)
            .where(Document.tenant_id == user.tenant_id)
            .where(Document.department_id == user.department_id)
            .where(Document.status != DocStatus.deleted)
            .where(Document.file_type == "folder")
        )
        return (await self.session.execute(q)).scalars().first()

class MetadataRepository(BaseRepository[Document]):

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.doc_cls = aliased(Document, name="doc_cls")


    

    async def _get_instance(self, document: Union[str, UUID], owner: TokenData):
        try:
            # сначала пытаемся как integer ID
            document_id = int(str(document))
            base_filter = self.doc_cls.id == document_id
        except ValueError:
            try:
                # или как UUID
                document_id = UUID(str(document))
                base_filter = self.doc_cls.id == document_id
            except ValueError:
                from urllib.parse import unquote
                decoded_name = unquote(document)
                base_filter = self.doc_cls.name == decoded_name

        stmt = (
            select(self.doc_cls)
            .where(self.doc_cls.tenant_id == owner.tenant_id)
            .where(self.doc_cls.department_id == owner.department_id)
            .where(self.doc_cls.deleted_at.is_(None))
            .where(base_filter)
            .where(
                or_(
                    self.doc_cls.status == "public",
                    self.doc_cls.owner_id == owner.id,
                    # если есть таблица shared_documents:
                    # self.doc_cls.id.in_(
                    #     select(shared.document_id).where(shared.user_id == owner.id)
                    # )
                )
            )
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def _extract_changes(document_patch: DocumentMetadataPatch) -> dict:

        if isinstance(document_patch, dict):
            return document_patch
        return document_patch.model_dump(exclude_unset=True)

    # Fields a client must never set through a patch, whatever the schema
    # happens to accept. Everything else the table has is fair game, so a column
    # added to `Document` later becomes patchable without anyone remembering to
    # update a list here.
    _PROTECTED_COLUMNS = frozenset({
        "id", "tenant_id", "department_id", "owner_id",
        "document_number", "created_at", "file_path", "file_hash",
    })

    @classmethod
    def _writable_changes(cls, changes: Dict[str, Any]) -> Dict[str, Any]:
        """
        Narrow a patch to fields that are actually columns on `Document`.

        `DocumentMetadataPatch` accepts `tags`, `categories` and `access_to`,
        none of which the table has. Passing them to `update().values()` raised
        a CompileError that `_execute_update` reported as "Ошибка при обновлении
        документа" — so renaming a document while sending tags looked like a
        name conflict. `access_to` is consumed separately by
        `_update_access_and_permission` before this runs.
        """
        allowed = set(Document.__table__.columns.keys()) - cls._PROTECTED_COLUMNS
        return {k: v for k, v in changes.items() if k in allowed}

    async def _execute_update(
        self, db_document: Document | Dict[str, Any], changes: Dict[str, Any]
    ) -> Document:

        if isinstance(db_document, dict):
            stmt = (
                update(Document)
                .where(Document.id == db_document.get("id"))
                .values(changes)
            )
            doc_name = db_document.get("name")
        else:
            stmt = (
                update(Document)
                .where(Document.id == db_document.id)
                .values(changes)
            )
            doc_name = db_document.name

        try:
            await self.session.execute(stmt)
        except Exception as e:
            raise http_409(msg=f"Ошибка при обновлении документа: {doc_name}") from e
        
    async def _find_existing(self, filename: str, user: TokenData, parent_id: Optional[int]) -> Optional[Document]:
        stmt = (
            select(Document)
            .where(Document.tenant_id == user.tenant_id)
            .where(Document.department_id == user.department_id)
            .where(Document.title == filename)
            .where(Document.deleted_at.is_(None))
        )
        if parent_id is None:
            stmt = stmt.where(Document.parent_id.is_(None))
        else:
            stmt = stmt.where(Document.parent_id == parent_id)
        result = await self.session.execute(stmt)
        return result.scalars().first()
        
        
    async def move_document(self, document_id: int, new_parent_id: int | None, user: TokenData):
        """
        Relocate a document or folder, on disk and in the database.

        This used to look for the source at
        `upload_dir/<tenant>/<department>/<file_path>`, while uploads write to
        `upload_dir/<file_path>` — `settings.upload_dir` *is* the
        tenant/department root. The source therefore never existed, the physical
        move was skipped by the `if old_abs.exists()` guard, and `file_path` was
        rewritten anyway. The row ended up pointing at a path with no file, the
        bytes stayed where nothing would look for them, and the old path — the
        only way back to them — was gone. Silent, unrecoverable data loss on
        every move.
        """
        doc = await self._get_scoped(document_id, user)
        if not doc:
            # Scoped, not a bare primary-key fetch: an admin of one tenant could
            # otherwise move another tenant's documents around.
            raise ValueError("Документ не найден")

        # permissions
        if doc.owner_id != user.id and user.role != "admin":
            raise ValueError("Нет прав")

        if new_parent_id is not None and int(new_parent_id) == int(document_id):
            raise ValueError("Нельзя переместить элемент в самого себя")

        # The subtree, by id. Used both to reject a move into your own
        # descendant and to re-anchor their paths below — the previous check
        # compared `file_path` strings, which is the very field this function
        # had been corrupting.
        descendants = await self._list_descendants_raw(doc)
        descendant_ids = {d.id for d in descendants}

        if new_parent_id:
            # Module-level helper taking `self` explicitly, not a method.
            parent = await _get_base_parent(self, new_parent_id, user)
            if not parent:
                raise ValueError("Целевая папка не найдена")
            if parent.id in descendant_ids:
                raise ValueError("Нельзя переместить элемент в собственную подпапку")

            new_rel = f"{parent.file_path}/{doc.name}" if parent.file_path else doc.name
        else:
            # move to root
            new_rel = doc.name

        old_rel = doc.file_path
        if new_rel == old_rel:
            return doc

        # `settings.upload_dir` already points at the tenant/department root —
        # see `_stream_and_hash`, which is what actually writes these files.
        uploads_root = Path(settings.upload_dir)
        old_abs = uploads_root / old_rel
        new_abs = uploads_root / new_rel

        if new_abs.exists():
            # `shutil.move` onto an existing directory moves *into* it, which
            # would nest the item one level below where the database says it is.
            raise ValueError("Элемент с таким именем уже существует в целевой папке")

        source_exists = old_abs.exists()
        if not source_exists and doc.file_type != "folder":
            # A folder legitimately has no directory of its own — `create_folder`
            # only inserts a row. A *file* without its bytes is an inconsistency,
            # and rewriting its path regardless is what caused this defect.
            raise FileNotFoundError(
                f"Файл отсутствует в хранилище: {old_rel}. Перемещение отменено."
            )

        # Apply the database changes and flush *before* touching the disk, so a
        # uniq_file / uq_title_parent violation surfaces while the filesystem is
        # still untouched.
        doc.parent_id = new_parent_id
        doc.file_path = new_rel

        old_prefix = old_rel.rstrip("/") + "/"
        for child in descendants:
            if child.file_path and child.file_path.startswith(old_prefix):
                # Re-anchored by slicing rather than `str.replace`, which is not
                # tied to the start of the string.
                child.file_path = new_rel + "/" + child.file_path[len(old_prefix):]
            else:
                # Already inconsistent — most likely orphaned by this very bug.
                # Inventing a path for it would compound the damage.
                logger.warning(
                    "move_document: descendant %s has path %r outside %r; left unchanged",
                    child.id, child.file_path, old_rel,
                )

        await self.session.flush()

        moved = False
        if source_exists:
            new_abs.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(old_abs), str(new_abs))
            moved = True

        try:
            await self.session.commit()
        except Exception:
            # Best effort, not a transaction: a filesystem and a database cannot
            # be made atomic here. Put the file back so the two still agree, and
            # record it if even that fails.
            if moved:
                try:
                    shutil.move(str(new_abs), str(old_abs))
                except Exception:
                    logger.exception(
                        "move_document: commit failed and %s could not be restored "
                        "to %s — the row and the file now disagree",
                        new_abs, old_abs,
                    )
            raise

        await self.session.refresh(doc)
        return doc

    
    async def _create_or_update_document(
        self,
        *,
        file: UploadFile,
        filename: str,
        file_path: str,
        file_hash: str,
        user: TokenData,
        existing: Optional[Document],
        parent_id: Optional[int] = None,
        size: Optional[int] = None,
        ) -> Document:
            if existing:
                values = dict(
                    file_path=file_path,
                    file_hash=file_hash,
                    size=size,
                    created_at=datetime.now(timezone.utc),
                    is_archived=False,
                    deleted_at=None,
                )
                if parent_id is not None and parent_id != existing.parent_id:
                    values["parent_id"] = parent_id

                stmt = (
                    update(Document)
                    .where(Document.id == existing.id)
                    .values(**values)
                    .returning(Document)
                )
                result = await self.session.execute(stmt)
                return result.scalar_one()

            new_doc = Document(
                name=filename,
                title=filename,
                tenant_id=user.tenant_id,
                department_id=user.department_id,
                owner_id=user.id,
                file_type="file",
                file_path=file_path,
                file_hash=file_hash,
                size=size,
                created_at=datetime.now(timezone.utc),
                parent_id=parent_id,
            )
            self.session.add(new_doc)
            await self.session.flush()
            return new_doc

    async def get_by_id_visible(self, doc_id: int, user: TokenData) -> Document:
        q = (
            select(Document)
            .where(
                Document.id == doc_id,
                Document.tenant_id == user.tenant_id,
                Document.department_id == user.department_id,
                # not deleted; tweak if you use another flag/enum
                Document.deleted_at.is_(None),
            )
        )
        doc = (await self.session.execute(q)).scalar_one_or_none()
        if not doc:
            raise http_404(msg=f"No document with id '{doc_id}' found.")
        return doc
    async def _list_children_raw(
        self,
        root_id: int,
        tenant_id: int,
        department_id: int,
    ) -> list[Document]:
        """
        Return ONLY direct children of root_id within the same tenant/department.
        This is a simple, non-recursive query for the /v2/children/{parent_id} endpoint.
        """
        result = await self.session.execute(
            select(Document)
            .where(
                Document.parent_id == root_id,
                Document.tenant_id == tenant_id,
                Document.department_id == department_id,
                # Trashed rows were included, so deleted files showed up in
                # folder listings and were written into the folder download ZIP.
                Document.status != DocStatus.deleted,
                Document.deleted_at.is_(None),
            )
            .order_by(Document.file_type.desc(), Document.name.asc(), Document.id.asc())
        )
        return result.scalars().all()
        


    async def _list_descendants_raw(self, root: Document) -> list[Document]:
        """
        Return ALL descendants of root (excluding the root itself).
        Uses a proper recursive CTE that references the CTE in the recursive term.
        """
        tenant_id = root.tenant_id
        department_id = root.department_id
        root_id = root.id

        # seed: the root within same tenant/department
        base = select(Document.id).where(
            Document.id == root_id,
            Document.tenant_id == tenant_id,
            Document.department_id == department_id,
        )
        cte = base.cte(name="tree", recursive=True)

        # recursive step - JOIN back to CTE
        step = (
            select(Document.id)
            .select_from(Document)
            .join(cte, Document.parent_id == cte.c.id)
            .where(
                Document.tenant_id == tenant_id,
                Document.department_id == department_id,
            )
        )
        cte = cte.union_all(step)

        # return ORM objects except the root
        result = await self.session.execute(
            select(Document)
            .join(cte, Document.id == cte.c.id)
            .where(Document.id != root_id)
        )
        return result.scalars().all()

    # Публичный метод (Pydantic схемы)
    # ───────────────────────────────
    async def list_children(
        self, user: TokenData, parent_id: Optional[int] = None, recursive: bool = False
    ) -> list[DocumentMetadataRead]:
        """
        List what is inside a folder, scoped to the caller.

        - `recursive=False`: the folder's direct children.
        - `recursive=True`: the whole subtree, excluding the root.

        The scope comes from `user`, never from the row being asked about. This
        previously read `getattr(self, "tenant_id", None)` — an attribute
        `__init__` never sets — and so always fell through to taking the tenant
        and department *from the requested folder*. `GET /v2/children/{id}` was
        therefore an enumeration oracle: any authenticated user could walk any
        tenant's library by incrementing an integer, and the folder-download ZIP
        inherited the same hole.

        A folder outside the caller's scope returns `[]` rather than 404, so the
        response cannot be used to tell "does not exist" from "not yours".
        """
        if parent_id is None:
            return []

        root_doc = await self._get_scoped(parent_id, user)
        if root_doc is None:
            return []

        if recursive:
            docs = await self._list_descendants_raw(root_doc)
            # `_list_descendants_raw` deliberately includes trashed rows — its
            # other callers (delete, permanent delete) need them. A listing does
            # not.
            docs = [
                d for d in docs
                if d.status != DocStatus.deleted and d.deleted_at is None
            ]
        else:
            docs = await self._list_children_raw(
                root_id=parent_id,
                tenant_id=user.tenant_id,
                department_id=user.department_id,
            )

        return await self._with_owners(
            [DocumentMetadataRead.model_validate(d, from_attributes=True) for d in docs]
        )

    async def get_document_for_callback(self, doc_id: int) -> Optional[Document]:
        """
        Look up a document for the OnlyOffice save callback.

        Unscoped by tenant on purpose: the callback comes from Document Server,
        not from a user session, so there is no `TokenData` to scope by. What
        stands in for it is the signed callback token, which is verified before
        this is reached — the caller must not invoke this on an unverified
        request.
        """
        result = await self.session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.status != DocStatus.deleted,
                Document.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()

    async def record_saved_content(self, doc: Document, *, size: int) -> None:
        """Keep the row in step with the bytes an editor session just wrote."""
        doc.size = size
        await self.session.flush()

    async def _get_scoped(self, doc_id: int, user: TokenData) -> Optional[Document]:
        """
        One live document within the caller's tenant and department, or None.

        Like `_get_base_parent` but without requiring a folder, and returning
        None instead of raising — callers here decide what an out-of-scope id
        should look like.
        """
        result = await self.session.execute(
            select(Document).where(
                Document.id == doc_id,
                Document.tenant_id == user.tenant_id,
                Document.department_id == user.department_id,
                # Both, not just one: `delete()` sets the pair together, but the
                # two have drifted apart in the data before (which is why
                # `doc_list` checks each of them separately too).
                Document.status != DocStatus.deleted,
                Document.deleted_at.is_(None),
            )
        )
        return result.scalar_one_or_none()


    async def _update_access_and_permission(self, db_document, changes, user_repo):

        access_given_to = changes.get("access_to", [])
        # if access_to has email ids, update doc_user_access table with doc_id and user_id
        for user_email in access_given_to:
            try:
                user_id = (
                    await user_repo.get_user(field="email", detail=user_email)
                ).__dict__["id"]
                # update doc_user_access table with doc_id and user_id
                await self._update_doc_user_access(db_document, user_id)

            except IntegrityError as e:
                raise http_409(msg=f"g '{user_email}' уже имеет доступ...") from e
            except AttributeError as e:
                raise http_404(
                    msg=f"Пользователь с адресом '{user_email}' не существует, убедитесь, что у пользователя есть аккаунт в DocFlow."
                ) from e

   


    async def _stream_and_hash(self, file: UploadFile, *, rel_file_path: str, user: TokenData):
        # `settings.upload_dir` already points at the tenant/department root
        # (LOCAL_STORAGE_PATH=.../uploads/1/1), which is also what `/files` and
        # the filesystem importer use. Appending tenant/department again wrote
        # uploads to .../uploads/1/1/1/1/... and stored a path that did not
        # match the imported documents.
        upload_root = Path(settings.upload_dir)

        file_path = upload_root / rel_file_path
        file_path.parent.mkdir(parents=True, exist_ok=True)

        sha256 = hashlib.sha256()
        total_size = 0
        with file_path.open("wb") as f:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                sha256.update(chunk)
                total_size += len(chunk)
        await file.seek(0)

        return sha256.hexdigest(), total_size, str(file_path.relative_to(upload_root))






    async def _update_doc_user_access(self, db_document, user_id):
        # The column is `document_id`, not `doc_id` — the old spelling raised
        # CompileError, so granting a user access to a document never worked.
        # `access_level` is NOT NULL with no default, so it has to be supplied.
        stmt = insert(doc_user_access).values(
            document_id=db_document.id,
            user_id=user_id,
            access_level=AccessLevel.read,
        )
        await self.session.execute(stmt)
        # No commit: this runs once per recipient from
        # `_update_access_and_permission`, so committing here would leave a
        # partial grant behind when a later recipient fails. The request's
        # session dependency commits once at the end.
        await self.session.flush()

    async def _delete_access(self, document) -> None:
        await self.session.execute(
            doc_user_access.delete().where(doc_user_access.c.document_id == document.id)
        )

    async def get_doc(self, filename: str) -> Dict[str, Any]:
        """
        Get document by filename irrespective of logged-in user.

        Args:
            self: The instance of the class.
            filename (str): The name of the document.

        Returns:
            Dict[str, Any]: The document metadata.
        """

        stmt = (
            select(Document)
            .where(Document.name == filename)
            .where(Document.deleted_at.is_(None))
            #.where(self.doc_cls.status != DocStatus.deleted)
        )
        result = await self.session.execute(stmt)
        # `.first()`, not `.scalar_one_or_none()`: `name` is deliberately not
        # unique (the same file name is legitimate in different folders), so
        # requiring exactly one row would raise once two exist. A stray
        # `fetchall()` used to consume the cursor here, making this return None
        # every time.
        return result.scalars().first()

    async def upload(
        self, document_upload: DocumentMetadataCreate
    ) -> DocumentMetadataRead:

        if not isinstance(document_upload, dict):
            db_document = Document(**document_upload.model_dump(exclude={"size", "tags", "categories", "file_hash", "access_to", "status"}))
        else:
            db_document = Document(**document_upload)

        try:
            self.session.add(db_document)
            await self.session.commit()
            await self.session.refresh(db_document)
        except IntegrityError as e:
            raise http_404(
                msg=f"Документ с именем: {document_upload.name} уже существует.",
            ) from e

        return await self._with_owner(DocumentMetadataRead(**db_document.__dict__))

    # Columns a client is allowed to sort by. Anything else falls back to
    # `name`, so a bad query string cannot reach the ORDER BY clause.
    SORTABLE_COLUMNS = {
        "name": Document.name,
        "size": Document.size,
        "created_at": Document.created_at,
        "file_type": Document.file_type,
    }

    @staticmethod
    def _order_by(sort_by: Optional[str], sort_dir: str, *, folders_first: bool = True):
        """
        A total ordering for a page of documents.

        Postgres gives no ordering guarantee without ORDER BY, so paging with
        OFFSET/LIMIT over an unordered query returns rows in whatever order the
        plan happens to produce — the same row can come back on two pages while
        another is never returned at all. Every listing query therefore ends
        with `id`, which is unique and so makes the order total.
        """
        column = MetadataRepository.SORTABLE_COLUMNS.get(
            (sort_by or "name").lower(), Document.name
        )
        # Names are compared case-insensitively; the raw column is left alone
        # for numeric and timestamp sorts.
        key = func.lower(column) if column is Document.name else column
        key = key.asc() if sort_dir != "desc" else key.desc()

        clauses = []
        if folders_first:
            # `file_type == 'folder'` sorts before everything else regardless of
            # the requested direction — folders on top is a layout rule, not a
            # sort the user asked for.
            clauses.append((Document.file_type == "folder").desc())
        clauses.append(key)
        clauses.append(Document.id.asc())
        return clauses

    @staticmethod
    def _escape_like(value: str) -> str:
        """
        Neutralise LIKE metacharacters in a literal.

        Without this a file called `отчёт_1` matches `отчётX1`, and one with a
        `%` in its name matches everything.
        """
        return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")

    @staticmethod
    def _escape_like_column(column):
        """
        The same escaping, applied in SQL rather than in Python.

        `_folder_sizes` builds its LIKE pattern out of a *column* — one folder's
        `file_path` — so there is no Python-side string to escape. The nesting
        order matters: backslashes first, or the escapes introduced by the later
        two would themselves be escaped.
        """
        escaped = func.replace(column, "\\", "\\\\")
        escaped = func.replace(escaped, "%", "\\%")
        return func.replace(escaped, "_", "\\_")

    @classmethod
    def _search_filter(cls, search: Optional[str]):
        """Case-insensitive substring match on the file name, or None."""
        term = (search or "").strip()
        if not term:
            return None
        return Document.name.ilike(f"%{cls._escape_like(term)}%", escape="\\")

    async def doc_list(
        self,
        owner: TokenData,
        parent_id: Optional[int] = None,
        recursive: bool = False,
        only_folders: bool = False,
        files_only: bool = False,        # ← NEW
        limit: int = 100,
        offset: int = 0,
        root_id: Optional[int] = None,        # ⟵ NEW
        search: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_dir: str = "asc",
    ):
        order_by = self._order_by(sort_by, sort_dir)
        search_filter = self._search_filter(search)

        # Guard: both flags at once is ambiguous
        if root_id is not None:
            # собираем всё поддерево root_id (включая сам корень)
            base = (
                select(Document)
                .where(Document.tenant_id == owner.tenant_id)
                .where(Document.department_id == owner.department_id)
                .where(Document.status != DocStatus.deleted)
            )
            if only_folders:
                base = base.where(Document.file_type == "folder")
            elif files_only:
                base = base.where(Document.file_type != "folder")

            # корень поддерева
            root_base = base.where(Document.id == root_id)

            # The recursive term has to join the CTE, not another alias of the
            # table. Joining `documents` to itself here selects every row that
            # has any parent — the whole library — so `root_id` stopped scoping
            # anything and a project-scoped search returned other projects' hits.
            cte = root_base.cte(name="subtree", recursive=True)

            d_child = aliased(Document)
            rec = (
                select(d_child)
                .join(cte, d_child.parent_id == cte.c.id)
                .where(d_child.tenant_id == owner.tenant_id)
                .where(d_child.department_id == owner.department_id)
                .where(d_child.status != DocStatus.deleted)
            )
            if only_folders:
                rec = rec.where(d_child.file_type == "folder")
            elif files_only:
                rec = rec.where(d_child.file_type != "folder")

            cte = cte.union_all(rec)

            # НЕрекурсивный режим: показываем «текущий уровень» внутри поддерева
            if not recursive:
                # parent_id=None трактуем как «дети root_id»
                effective_parent = root_id if parent_id is None else parent_id

                level = (
                    select(Document)
                    .join(cte, cte.c.id == Document.id)
                    .where(Document.parent_id == effective_parent)
                )
                if search_filter is not None:
                    level = level.where(search_filter)

                rows_q = level.order_by(*order_by).offset(offset).limit(limit)
                cnt_q = select(func.count()).select_from(
                    level.with_only_columns(Document.id).order_by(None).subquery()
                )
                total = (await self.session.execute(cnt_q)).scalar_one()
                docs  = (await self.session.execute(rows_q)).scalars().all()
                return await self._serialize_with_folder_sizes(docs, int(total), owner, with_sizes=not only_folders)

            # Рекурсивный режим: отдаём всё поддерево (с пагинацией/фильтрами)
            subtree = select(Document).join(cte, cte.c.id == Document.id)
            if search_filter is not None:
                subtree = subtree.where(search_filter)

            rows_q = subtree.order_by(*order_by).offset(offset).limit(limit)
            cnt_q = select(func.count()).select_from(
                subtree.with_only_columns(Document.id).order_by(None).subquery()
            )
            total  = (await self.session.execute(cnt_q)).scalar_one()
            docs   = (await self.session.execute(rows_q)).scalars().all()
            return await self._serialize_with_folder_sizes(docs, int(total), owner, with_sizes=not only_folders)

        if only_folders and files_only:
            files_only = False  # or raise ValueError("only_folders and files_only are mutually exclusive")

        base = (
            select(Document)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
        )

        # Kind filter
        if only_folders:
            base = base.where(Document.file_type == "folder")
        elif files_only:
            # adapt to your model: either `is_folder = False` or file_type != "folder"
            base = base.where(Document.file_type != "folder")

        if search_filter is not None:
            base = base.where(search_filter)

        if not recursive:
            # Current level only
            if parent_id is None:
                base = base.where(Document.parent_id.is_(None))
            else:
                base = base.where(Document.parent_id == parent_id)

            # Count first
            count_stmt = base.with_only_columns(func.count()).order_by(None)
            total_count = (await self.session.execute(count_stmt)).scalar_one()

            # Page
            stmt = base.order_by(*order_by).offset(offset).limit(limit)
            docs = (await self.session.execute(stmt)).scalars().all()

            return await self._serialize_with_folder_sizes(docs, int(total_count), owner, with_sizes=not only_folders)

        # Recursive branch
        parent_filter = (
            Document.parent_id.is_(None) if parent_id is None else Document.parent_id == parent_id
        )

        # re-apply base with same filters (tenant/department/status + kind + parent)
        base = (
            select(Document)
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status != DocStatus.deleted)
            .where(parent_filter)
        )
        if only_folders:
            base = base.where(Document.file_type == "folder")
        elif files_only:
            base = base.where(Document.file_type != "folder")

        # As in the root_id branch: the recursive term must join the CTE. Joining
        # `documents` to a second alias of itself matched every row with a
        # parent, so a recursive listing returned unrelated folders and repeated
        # rows through the UNION ALL.
        cte = base.cte(name="recursive_docs", recursive=True)

        child = aliased(Document)
        recursive_q = (
            select(child)
            .join(cte, child.parent_id == cte.c.id)
            .where(child.tenant_id == owner.tenant_id)
            .where(child.department_id == owner.department_id)
            .where(child.status != DocStatus.deleted)
        )

        if only_folders:
            recursive_q = recursive_q.where(child.file_type == "folder")
        elif files_only:
            recursive_q = recursive_q.where(child.file_type != "folder")

        cte = cte.union_all(recursive_q)

        # The search term filters the *result*, not the walk: a match nested
        # under a non-matching folder still has to be reachable.
        descendants = select(Document).join(cte, Document.id == cte.c.id)
        if search_filter is not None:
            descendants = descendants.where(search_filter)

        rows_stmt = descendants.order_by(*order_by).offset(offset).limit(limit)

        count_stmt = select(func.count()).select_from(
            descendants.with_only_columns(Document.id).order_by(None).subquery()
        )
        total = (await self.session.execute(count_stmt)).scalar_one()

        docs = (await self.session.execute(rows_stmt)).scalars().all()

        return await self._serialize_with_folder_sizes(docs, int(total), owner, with_sizes=not only_folders)

    async def _folder_sizes(self, folders: list[Document], owner: TokenData) -> dict[int, int]:
        """
        Total bytes contained in each folder.

        The hierarchy is already encoded in `file_path`, so one prefix query per
        page beats a recursive walk (or a query per folder).
        """
        wanted = [f for f in folders if (f.file_path or "").strip()]
        if not wanted:
            return {}

        parent = aliased(Document)
        child = aliased(Document)

        # The pattern comes from a column, so it has to be escaped in SQL. A
        # folder called `2024_Q1` otherwise matched `2024XQ1/...` and reported
        # the neighbouring folder's bytes as its own.
        #
        # Note this join can never use ix_documents_file_path_prefix — the
        # pattern is not a constant — so do not "simplify" the escaping away in
        # the hope of getting an index scan. There was never one to get.
        prefix = self._escape_like_column(parent.file_path).concat("/%")

        stmt = (
            select(parent.id, func.coalesce(func.sum(child.size), 0))
            .select_from(parent)
            .join(child, child.file_path.like(prefix, escape="\\"))
            .where(parent.id.in_([f.id for f in wanted]))
            .where(child.tenant_id == owner.tenant_id)
            .where(child.department_id == owner.department_id)
            .where(child.deleted_at.is_(None))
            .where(child.file_type != "folder")
            .group_by(parent.id)
        )

        rows = (await self.session.execute(stmt)).all()
        return {row[0]: int(row[1] or 0) for row in rows}

    async def _owner_labels(self, rows) -> dict[str, tuple[Optional[str], Optional[str]]]:
        """
        `owner_id` → (username, email) for a page of documents.

        One query for the whole page, not one per row: `Document.owner` is a
        lazy relationship and touching it from async code raises
        MissingGreenlet, while eager-loading it on every listing query would
        pull a full user row per document.
        """
        ids = {r.owner_id for r in rows if getattr(r, "owner_id", None)}
        if not ids:
            return {}

        result = await self.session.execute(
            select(User.id, User.username, User.email).where(User.id.in_(ids))
        )
        return {row[0]: (row[1], row[2]) for row in result.all()}

    @staticmethod
    def _apply_owner(read: DocumentMetadataRead, labels: dict) -> DocumentMetadataRead:
        """Fill `owner_name`/`owner_email` in place; unknown owners stay None."""
        username, email = labels.get(read.owner_id, (None, None))
        read.owner_name = username or email
        read.owner_email = email
        return read

    async def _with_owners(self, reads: list[DocumentMetadataRead]) -> list[DocumentMetadataRead]:
        labels = await self._owner_labels(reads)
        return [self._apply_owner(r, labels) for r in reads]

    async def _with_owner(self, read: DocumentMetadataRead) -> DocumentMetadataRead:
        return self._apply_owner(read, await self._owner_labels([read]))

    async def serialize_one(self, doc: Document) -> DocumentMetadataRead:
        """A single row as the API returns it, owner resolved."""
        return await self._with_owner(
            DocumentMetadataRead.model_validate(doc, from_attributes=True)
        )

    async def _serialize_with_folder_sizes(
        self, docs: list[Document], total: int, owner: TokenData,
        with_sizes: bool = True,
    ) -> dict:
        """
        Serialize a page of documents, filling in aggregated folder sizes.

        `with_sizes=False` skips the aggregation entirely — the folder tree asks
        for every folder at once and never renders a size, so paying for the
        prefix scan there would stall the request on a large library.
        """
        folders = [d for d in docs if d.file_type == "folder"] if with_sizes else []
        sizes = await self._folder_sizes(folders, owner)
        labels = await self._owner_labels(docs)

        items = []
        for doc in docs:
            read = DocumentMetadataRead.model_validate(doc, from_attributes=True)
            if doc.file_type == "folder":
                read.size = sizes.get(doc.id, 0)
            items.append(self._apply_owner(read, labels))

        return {"documents": items, "total_count": total}


    async def list_folders(self, owner: TokenData):
        """
        Every folder the caller can see — the source for the "move to" picker.

        `owner` was already a parameter and simply went unused: there were no
        filters at all, so this handed each caller the complete folder tree of
        every tenant in the database, soft-deleted folders included.
        """
        q = (
            select(self.doc_cls.id, self.doc_cls.name, self.doc_cls.parent_id)
            .where(self.doc_cls.file_type == "folder")
            .where(self.doc_cls.tenant_id == owner.tenant_id)
            .where(self.doc_cls.department_id == owner.department_id)
            .where(self.doc_cls.status != DocStatus.deleted)
            .where(self.doc_cls.deleted_at.is_(None))
            .order_by(self.doc_cls.parent_id.nullsfirst(), self.doc_cls.name)
        )
        rows = (await self.session.execute(q)).all()
        return {"folders": [{"id": r[0], "name": r[1], "parent_id": r[2]} for r in rows]}


    async def get(
        self, document: Union[str, UUID], owner: TokenData
    ) -> Union[DocumentMetadataRead, HTTPException]:

        db_document = await self._get_instance(document=document, owner=owner)
        if db_document is None:
            raise http_409(msg=f"No Document with {document}")

        return await self._with_owner(DocumentMetadataRead(**db_document.__dict__))

    async def patch(
        self,
        document: Union[str, UUID],
        document_patch: DocumentMetadataPatch,
        owner: TokenData,
        user_repo: AuthRepository,
        is_owner: bool,
    ) -> Union[DocumentMetadataRead, HTTPException]:

        if is_owner:
            db_document = await self._get_instance(document=document, owner=owner)
            if db_document is None:
                raise http_404(msg=f"No Document with: {document}")
            changes = await self._extract_changes(document_patch)

            # Reads `access_to` — so it has to run before the patch is narrowed
            # to real columns below.
            await self._update_access_and_permission(db_document, changes, user_repo)

            writable = self._writable_changes(changes)
            # `update().values({})` is itself an error, and a patch carrying only
            # tags is a legitimate no-op now that they are filtered out.
            if writable:
                await self._execute_update(db_document, writable)
                await self.session.refresh(db_document)

        else:
            # This condition will be activated when, the new version of file is added by a privileged memberment.
            db_document = await self.get_doc(filename=str(document))
            if db_document is None:
                raise http_404(msg=f"No Document with: {document}")
            changes = self._writable_changes(await self._extract_changes(document_patch))

            if changes:
                await self._execute_update(db_document, changes)
                await self.session.refresh(db_document)

        return await self._with_owner(DocumentMetadataRead(**db_document.__dict__))
    async def delete(self, document: Union[str, int, UUID], owner: TokenData) -> None:
        try:
            # 1) читаем корень в рамках tenant/department (как ты уже сделал в _get_instance)
            db_document = await self._get_instance(document=document, owner=owner)
            if db_document is None:
                raise http_404(msg=f"No document found with identifier: {document}")

            # 2) собираем потомков ТОЛЬКО под тем же tenant/department
            descendants: list[Document] = []
            if db_document.file_type == "folder":
                descendants = await self._list_descendants_raw(db_document)  # см. реализацию ниже

            ids = [db_document.id, *(d.id for d in descendants)]
            now = datetime.now(timezone.utc)

            # 3) операции без открытия своей транзакции
            async def _apply():
                # ВАЖНО: ни здесь, ни в вызываемых функциях не делай commit()/rollback()
                # чистим доступы/шары/локи bulk-ом, если они есть
            
                # мягкое удаление всех узлов одним апдейтом
                await self.session.execute(
                    update(Document)
                    .where(Document.id.in_(ids))
                    # Don't overwrite a row that was already in the bin: a file
                    # trashed on its own keeps the moment *it* was trashed, so
                    # the bin's "deleted at" column tells the truth. Without
                    # this, deleting the parent folder restamps its whole
                    # subtree and that history is gone.
                    .where(Document.status != DocStatus.deleted)
                    .values(
                        deleted_at=now,
                        status=DocStatus.deleted,
                        # The bin is keyed off this, not off `owner_id` —
                        # see `_trashed_by`.
                        deleted_by=owner.id,
                    )
                )

            # 4) если уже есть транзакция — просто выполняем; если нет — откроем свою
            if self.session.in_transaction():
                await _apply()
            else:
                async with self.session.begin():
                    await _apply()

        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Delete failed for %s", document)  # даст полный стек
            raise http_404(msg=f"Failed to delete document: {document}") from e

    @staticmethod
    def _trashed_by(owner: TokenData):
        """
        Rows that belong in *this* caller's bin.

        The bin lists what the user deleted, not what the user owns. Those are
        different sets: `delete()` (through `_get_instance`) accepts any row
        that is `public` inside the caller's tenant/department, and everything
        the filesystem importer created is `public` under one synthetic
        `OWNER_ID`. Scoping the bin by `owner_id` therefore made the ordinary
        case — deleting an imported file — look like data loss: the row left
        every listing and turned up in no bin, and `restore` refused it too.

        `deleted_by IS NULL` is a row trashed before that column existed; those
        fall back to the old rule so an existing bin does not empty itself on
        deploy.
        """
        return or_(
            Document.deleted_by == owner.id,
            and_(Document.deleted_by.is_(None), Document.owner_id == owner.id),
        )

    @staticmethod
    def _parent_is_trashed():
        """
        True when this row's parent is itself in the bin.

        Correlated against the enclosing `Document`, so it composes into any
        query over it. `parent_id IS NULL` needs no special case — the join
        matches nothing, so a top-level row is never "inside" a trashed folder.

        Deliberately not scoped by owner: `delete()` cascades through
        `_list_descendants_raw`, which is scoped by tenant/department and *not*
        by owner, so a colleague's file inside your folder is already trashed by
        your action. The bin has to agree, or that file surfaces as a phantom
        top-level entry whose restore produces a live row under a deleted parent
        — invisible in every listing.
        """
        parent = aliased(Document, name="trash_parent")
        return (
            select(parent.id)
            .where(parent.id == Document.parent_id)
            .where(parent.status == DocStatus.deleted)
            .exists()
        )

    async def bin_list(self, owner: TokenData) -> dict:
        """
        The bin, listing only what the user actually deleted.

        A folder and everything under it are marked identically by `delete()`,
        so listing every row with `status == deleted` put one entry in the bin
        per file — deleting a folder of 40 files produced 41 rows. Like Google
        Drive, only "trash roots" are listed: a deleted row whose parent is not
        also deleted. Restoring one brings its whole subtree back.
        """
        stmt = (
            select(Document)
            .where(self._trashed_by(owner))
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status == DocStatus.deleted)
            .where(~self._parent_is_trashed())
            .order_by(
                Document.deleted_at.desc().nullslast(),
                (Document.file_type == "folder").desc(),
                func.lower(Document.name),
                Document.id,
            )
        )
        result = await self.session.scalars(stmt)
        docs = await self._with_owners([
            DocumentMetadataRead.model_validate(doc, from_attributes=True)
            for doc in result
        ])
        return {"response": docs, "no_of_docs": len(docs)}

    #: What a restored document's status becomes.
    #:
    #: `delete()` overwrites `status`, so the value a document had before it was
    #: trashed is not recorded anywhere and cannot be put back. This used to be
    #: `private`, which at subtree scale is destructive: the importer writes
    #: every row as `public` and `_get_instance` admits a document only when it
    #: is `public` or owned by the caller, so restoring a folder would make its
    #: contents unreachable to everyone but its owner. `public` matches how
    #: essentially every row in this deployment was created.
    #:
    #: The real fix is to stop overwriting `status` at all and use `deleted_at`
    #: as the sole trash marker — a wider change, since ~18 filters test the
    #: status and `ix_documents_scope` is built on it.
    RESTORED_STATUS = DocStatus.public

    async def restore(self, doc_id: int, owner: TokenData) -> DocumentMetadataRead:
        """
        Take a document out of the bin, together with everything under it.

        This used to match by *name* through a scan of the bin and restore that
        single row — so restoring a folder left its contents deleted, and
        restoring a nested file produced a live row under a deleted parent,
        which no listing will show and `_collect_purgeable` then refuses to
        permanently delete.
        """
        root = (
            await self.session.execute(
                select(Document)
                .where(Document.id == doc_id)
                .where(self._trashed_by(owner))
                .where(Document.tenant_id == owner.tenant_id)
                .where(Document.department_id == owner.department_id)
                .where(Document.status == DocStatus.deleted)
            )
        ).scalar_one_or_none()

        if root is None:
            raise http_404(msg=f"No document in the bin with id: {doc_id}")

        # The bin no longer offers a nested row, but a direct API call could ask
        # for one. Restoring it would strand it under a deleted parent.
        parent_trashed = await self.session.scalar(
            select(
                select(Document.id)
                .where(Document.id == root.parent_id)
                .where(Document.status == DocStatus.deleted)
                .exists()
            )
        )
        if parent_trashed:
            raise http_409(
                msg="Сначала восстановите родительскую папку."
            )

        descendants = await self._list_descendants_raw(root)
        ids = [
            root.id,
            # Only rows this delete actually trashed. A live descendant — the
            # status/deleted_at drift that exists in this data — is left alone.
            *(d.id for d in descendants if d.status == DocStatus.deleted),
        ]

        await self.session.execute(
            update(Document)
            .where(Document.id.in_(ids))
            .values(deleted_at=None, status=self.RESTORED_STATUS, deleted_by=None)
        )
        # Flush, not commit — matches `perm_delete_a_doc`; the request's session
        # dependency commits once at the end.
        await self.session.flush()
        await self.session.refresh(root)

        return await self._with_owner(
            DocumentMetadataRead.model_validate(root, from_attributes=True)
        )

    async def _purge_dependents(self, ids: list[int]) -> None:
        """
        Remove every row that references these documents.

        `Document.children` carries `cascade="all, delete"`, but that is an *ORM*
        cascade and a Core `delete()` statement bypasses it entirely — so a bare
        DELETE hit a ForeignKeyViolation from `document_versions`,
        `shared_documents`, `share_links` or `permissions`.
        """
        if not ids:
            return

        await self.session.execute(
            doc_user_access.delete().where(doc_user_access.c.document_id.in_(ids))
        )
        await self.session.execute(
            delete(DocumentVersion).where(DocumentVersion.document_id.in_(ids))
        )
        await self.session.execute(
            delete(ShareLink).where(ShareLink.document_id.in_(ids))
        )
        await self.session.execute(
            delete(SharedDocument).where(SharedDocument.document_id.in_(ids))
        )

    async def _collect_purgeable(self, doc: Document) -> list[int]:
        """
        `doc` and its whole subtree, provided every part of it is in the bin.

        A child can be live under a trashed parent: `restore()` restores one row
        by name, and does not touch its ancestors. Removing the parent would then
        orphan a document the user asked to keep.
        """
        descendants = await self._list_descendants_raw(doc)
        restored = [
            d for d in descendants
            if d.status != DocStatus.deleted and d.deleted_at is None
        ]
        if restored:
            raise http_409(
                msg=(
                    f"«{doc.name}» содержит восстановленные элементы "
                    f"({len(restored)}) — сначала удалите или переместите их."
                )
            )
        return [doc.id, *(d.id for d in descendants)]

    async def perm_delete_a_doc(self, document: UUID | None, owner: TokenData) -> None:
        result = await self.session.execute(
            select(Document)
            .where(self._trashed_by(owner))
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.id == document)
            .where(Document.status == DocStatus.deleted)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise http_404(msg=f"No document in the bin with id: {document}")

        ids = await self._collect_purgeable(doc)
        await self._purge_dependents(ids)

        # One statement for parents and children together: referential integrity
        # is checked at end-of-statement, so no depth ordering is needed. Deleting
        # only the requested row left its trashed descendants pointing at a
        # parent that no longer existed.
        await self.session.execute(delete(Document).where(Document.id.in_(ids)))
        await self.session.flush()

    async def empty_bin(self, owner: TokenData) -> dict:
        """
        Empty the caller's bin.

        A folder that still holds a restored item is skipped and named in the
        result rather than failing the whole call — one awkward row should not
        stop the rest of the bin from being emptied.
        """
        result = await self.session.execute(
            select(Document)
            .where(self._trashed_by(owner))
            .where(Document.tenant_id == owner.tenant_id)
            .where(Document.department_id == owner.department_id)
            .where(Document.status == DocStatus.deleted)
            # Trash roots only — the same rows the bin shows. Iterating every
            # trashed row instead worked, but a folder that had to be skipped
            # was named by whichever nested row was reached first, which is not
            # something the user has seen. Ordering by `parent_id` was also
            # described as "shallowest first" and is not: it orders by the id
            # value, not by depth.
            .where(~self._parent_is_trashed())
            .order_by(Document.id)
        )
        trashed = result.scalars().all()

        purge: set[int] = set()
        skipped: list[str] = []

        for doc in trashed:
            if doc.id in purge:
                continue
            try:
                purge.update(await self._collect_purgeable(doc))
            except HTTPException:
                skipped.append(doc.name)

        ids = sorted(purge)
        await self._purge_dependents(ids)
        if ids:
            await self.session.execute(delete(Document).where(Document.id.in_(ids)))
        await self.session.flush()

        return {"deleted": len(ids), "skipped": skipped}

    async def archive(self, document: str, user: TokenData) -> DocumentMetadataRead:

        doc = await self._get_instance(document=document, owner=user)

        if doc and doc.status != DocStatus.archived:
            # Keep both flags in step: the list endpoints and the UI read
            # `is_archived`, while the status drives the archive page.
            change = {"status": DocStatus.archived, "is_archived": True}
            await self._execute_update(db_document=doc, changes=change)
            return await self._with_owner(DocumentMetadataRead(**doc.__dict__))

        if doc and doc.status == DocStatus.archived:
            raise http_409(msg="Документ уже в архиве")

        raise http_404(msg="Документ не существует")


    async def un_archive(self, file: str, user: TokenData) -> DocumentMetadataRead:

        doc = await self._get_instance(document=file, owner=user)

        if doc and doc.status == DocStatus.archived:
            change = {"status": "private", "is_archived": False}
            await self._execute_update(db_document=doc, changes=change)
            return await self._with_owner(DocumentMetadataRead(**doc.__dict__))
        if doc and doc.status != DocStatus.archived:
            raise http_409(msg="Document is not archived")
        raise http_404(msg="Document does not exits")

   

    async def create_folder(
        self,
        owner_id: str,
        tenant_id: int,
        department_id: Optional[int],
        data: FolderCreate,
    ):
        folder_name = (data.name or "").strip()
        if not folder_name:
            raise ValueError("Folder name is required")

        # вычисляем file_path для папки
        parent_path = ""
        if data.parent_id:
            parent = await self.session.get(Document, data.parent_id)
            if not parent:
                raise ValueError("Parent folder not found")
            # Берём путь родителя (если по каким-то причинам пустой — fallback на имя)
            parent_path = (parent.file_path or parent.name or "").strip()

        def join_path(a: str, b: str) -> str:
            if not a:
                return b
            if a.endswith("/"):
                a = a[:-1]
            return f"{a}/{b}"

        file_path = join_path(parent_path, folder_name) if parent_path else folder_name

        folder = Document(
            owner_id=owner_id,
            tenant_id=tenant_id,
            department_id=department_id,
            file_type="folder",
            document_number=None,          # или генерируй, если нужно
            title=getattr(data, "title", None) or folder_name,
            name=folder_name,
            status="draft",
            file_path=file_path,           # <-- БОЛЬШЕ НЕ NULL
            file_hash=None,
            parent_id=data.parent_id,
        )

        self.session.add(folder)
        try:
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(folder)
        return folder

    async def archive_document(self, document_id: UUID):
        stmt = update(Document).where(Document.id == document_id).values(is_archived=True)
        await self.session.execute(stmt)
        await self.session.commit()

    async def is_document_archived(self, document_id: UUID) -> bool:
        stmt = select(Document.is_archived).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def toggle_favourited(self, document_id: UUID):
        stmt = select(Document.is_favourited).where(Document.id == document_id)
        result = await self.session.execute(stmt)
        is_favourited = result.scalar_one_or_none()

        stmt = update(Document).where(Document.id == document_id).values(is_favourited=not is_favourited)
        await self.session.execute(stmt)
        await self.session.commit()


    async def archive_list(self, user: TokenData):
        stmt = (
            select(Document)
            .where(Document.owner_id == user.id)
            .where(
                (Document.is_archived == True) | 
                (Document.status == DocStatus.archived)
            )
            .where(Document.deleted_at.is_(None))
        )
        
        result = (await self.session.execute(stmt)).scalars().all()
        docs = await self._with_owners([DocumentMetadataRead.from_orm(doc) for doc in result])
        return {"documents": docs, "count": len(result)}

    async def favorited_list(self, user: TokenData):
        # NB: this used to be `is_favourited OR status == public`, which matched
        # every public document and returned the whole library.
        stmt = (
            select(Document)
            .where(Document.owner_id == user.id)
            .where(Document.is_favourited.is_(True))
            .where(Document.deleted_at.is_(None))
            .order_by(Document.name)
        )

        result = (await self.session.execute(stmt)).scalars().all()
        docs = await self._with_owners([DocumentMetadataRead.from_orm(doc) for doc in result])
        return {"documents": docs, "count": len(result)}




    async def get_folder_by_name_and_parent(self, name: str, parent_id: UUID, owner_id: str):
        stmt = (
            select(Document)
            .where(Document.name == name)
            .where(Document.parent_id == parent_id)
            .where(Document.owner_id == owner_id)
            .where(Document.type == "folder")
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_folder_by_id(self, folder_id: UUID, owner_id: str):
        stmt = (
            select(Document)
            .where(Document.id == folder_id)
            .where(Document.parent_id == None )
            .where(Document.owner_id == owner_id)
            .where(Document.type == "folder")
            .where(Document.status != DocStatus.deleted
            )  # Ensure the folder is not deleted   
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()  # <-- Добавь это

    async def get_existing_folders(self, folder_paths: List[str], tenant_id: UUID) -> List[Document]:
        stmt = (
            select(Document)
            .where(Document.file_type == "folder")
            .where(Document.tenant_id == tenant_id)
            .where(Document.file_path.in_(folder_paths))
            .where(Document.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


    async def bulk_create_folders(
        self,
        folder_paths: list[str],
        *,
        tenant_id,
        user_id,
        department_id,
        base_parent_id: int | None = None,
        user: TokenData | None = None,              # optional (for convenience)
    ) -> dict[str, int]:
        # Normalize to posix
        folder_paths = [PurePosixPath(p).as_posix().strip("/") for p in folder_paths]

        base_parent: Document | None = None
        base_parent: Document | None = None
        base_prefix = ""
        if base_parent_id is not None:   # ← строго проверяем на None
            base_parent = await self.session.get(Document, base_parent_id)
            if not base_parent or base_parent.file_type != "folder":
                raise HTTPException(status_code=404, detail="Target folder not found")
            base_prefix = (base_parent.file_path or base_parent.name or "").strip("/")


        final_paths: list[str] = []
        for p in folder_paths:
            final_paths.append(await _join_posix(base_prefix, p) if base_prefix else p)

        # Preload existing
        existing = await self.get_existing_folders(final_paths, tenant_id)
        path_to_id: dict[str, int] = {f.file_path: f.id for f in existing}

        # Create in topological order
        for rel_path in sorted(folder_paths):
            rel_path = rel_path.strip().lstrip("./").strip("/")
            if not rel_path or rel_path == ".":
                continue
            final_path = await _join_posix(base_prefix, rel_path) if base_prefix else rel_path
            if final_path in path_to_id:
                continue

            parent_rel = "/".join(rel_path.split("/")[:-1]) if "/" in rel_path else None
            parent_final = await _join_posix(base_prefix, parent_rel) if parent_rel else base_prefix or None
            
            if not parent_rel and base_parent_id:
                parent_id = base_parent_id
            else:
                parent_id = path_to_id.get(parent_final)
            name = rel_path.split("/")[-1]
            if not name or name == ".":
                continue


            folder = Document(
                name=name,
                title=name,
                file_type="folder",
                parent_id=parent_id,
                tenant_id=tenant_id,
                department_id=department_id,
                owner_id=user_id,
                status=DocStatus.private,
                is_archived=False,
                is_favourited=False,
                file_path=final_path,  # ← IMPORTANT
                created_at=datetime.now(timezone.utc),
            )
            self.session.add(folder)
            await self.session.flush()
            path_to_id[final_path] = folder.id

        return path_to_id

    async def upload_with_streaming(
        self,
        *,
        file: UploadFile,
        folder: str | None,            # relative path (webkitRelativePath)
        filename: str,
        user: TokenData,
        parent_map: dict[str, int],
        base_parent_id: int | None = None,
    ):
        base_parent = await _get_base_parent(self, base_parent_id, user)
        base_prefix = (base_parent.file_path or base_parent.name or "").strip("/") if base_parent else ""

        # Нормализуем относительный путь
        folder = PurePosixPath(folder or "").as_posix().strip("/")
        if not folder or folder == ".":
            folder = None

        # Если folder пустой → значит грузим прямо в выбранную папку (base_parent)
        if folder is None:
            final_folder_path = None
            parent_id = base_parent_id
        else:
            # Есть подпапка → вычисляем полный путь
            final_folder_path = await _join_posix(base_prefix, folder) if base_prefix else folder
            parent_id = parent_map.get(final_folder_path)

            # Если подпапки нет в parent_map → создать её на лету
            if parent_id is None:
                folder_name = final_folder_path.split("/")[-1]
                parent_rel = "/".join(final_folder_path.split("/")[:-1]) or None
                parent_parent_id = parent_map.get(parent_rel) if parent_rel else base_parent_id

                new_folder = Document(
                    name=folder_name,
                    title=folder_name,
                    tenant_id=user.tenant_id,
                    department_id=user.department_id,
                    owner_id=user.id,
                    file_type="folder",
                    file_path=final_folder_path,
                    parent_id=parent_parent_id,
                    status=DocStatus.private,
                    created_at=datetime.now(timezone.utc),
                    is_archived=False,
                    is_favourited=False,
                )
                self.session.add(new_folder)
                await self.session.flush()
                parent_id = new_folder.id
                parent_map[final_folder_path] = parent_id

        # Формируем путь для файла
        rel_file_path = (
            await _join_posix(base_prefix, filename) if folder is None else await _join_posix(final_folder_path, filename)
        )

        # Сохраняем файл
        file_hash, file_size, stored_rel_path = await self._stream_and_hash(
            file, rel_file_path=rel_file_path, user=user
        )

        logger.info("upload_with_streaming: base_prefix=%s, folder=%s, final_folder_path=%s, parent_id=%s",
                    base_prefix, folder, final_folder_path, parent_id)

        existing = await self._find_existing(filename, user, parent_id)
        if existing and existing.file_hash == file_hash:
            return {"response": "no_change", "document": existing}

        document = await self._create_or_update_document(
            file=file,
            filename=filename,
            file_path=stored_rel_path,
            file_hash=file_hash,
            user=user,
            existing=existing,
            parent_id=parent_id,
            size=file_size,
        )
        return {"response": "success", "document": document}
