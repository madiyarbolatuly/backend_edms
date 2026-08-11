from typing import List

from app.api.dependencies.constants import SUPPORTED_FILE_TYPES
from app.schemas.documents.documents_metadata import DocumentMetadataRead


def _split(csv: str) -> List[str]:
    """"a, b ,c" -> ["a", "b", "c"], dropping empties."""
    return [part.strip() for part in csv.split(",") if part.strip()]


class DocumentOrgRepository:
    """
    In-memory filtering over a page of documents.

    Every predicate here used to be written as
    `result.extend(doc for tag in tags if ...)` where `doc` was a dict — which
    extends the list with the dict's *keys*, so a filtered search returned a
    list of field names rather than documents. The filters are now plain
    predicates and `search_doc` applies them as an AND, which is what the
    endpoint's query parameters read like.
    """

    def __init__(self): ...

    @staticmethod
    def _has_tag(doc: DocumentMetadataRead, tags: List[str]) -> bool:
        return bool(doc.tags) and any(tag in doc.tags for tag in tags)

    @staticmethod
    def _is_file_type(doc: DocumentMetadataRead, extensions: List[str]) -> bool:
        """
        `file_type` holds a MIME type for uploads and the literal "folder" for
        folders, while the query parameter is an extension ("pdf,docx").
        """
        if not doc.file_type:
            return False
        wanted_mimes = {
            mime for mime, ext in SUPPORTED_FILE_TYPES.items() if ext in extensions
        }
        return doc.file_type in wanted_mimes or doc.file_type in extensions

    @staticmethod
    def _has_status(doc: DocumentMetadataRead, statuses: List[str]) -> bool:
        # `status` is a str-subclassed enum, so compare against its value rather
        # than the "DocStatus.public" repr the old code matched on.
        current = getattr(doc.status, "value", doc.status)
        return str(current) in statuses

    async def search_doc(
        self,
        docs: List[DocumentMetadataRead],
        tags: str = None,
        categories: str = None,
        file_types: str = None,
        status: str = None,
    ) -> List[DocumentMetadataRead]:
        """
        Narrow `docs` by every filter that was supplied.

        Returns a flat list in the same shape as the unfiltered branch of the
        endpoint, so a caller does not have to care whether filters were used.
        `categories` is accepted for signature compatibility and must be empty —
        the read schema has no such field, so the route rejects it up front.
        """
        result = list(docs)

        if tags:
            wanted = _split(tags)
            result = [d for d in result if self._has_tag(d, wanted)]

        if file_types:
            wanted = _split(file_types)
            result = [d for d in result if self._is_file_type(d, wanted)]

        if status:
            wanted = _split(status)
            result = [d for d in result if self._has_status(d, wanted)]

        return result
