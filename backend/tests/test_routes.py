"""
The API's routing table.

Two things are pinned here.

First, the paths the frontend builds in `src/config/api.ts`. Those are hand-
written strings; when a router prefix changes, nothing on either side complains
until a button 404s in production. The frontend has the mirror image of this
test.

Second, the doubled prefixes. `/v2/folders/folders/...` and
`/v2/office/office/...` look like typos — the sub-router carries a prefix and is
then mounted under the same one again. They are load-bearing: the deployed
frontend calls those paths. Asserting them keeps someone from "fixing" the
router and breaking folder creation and the editor.
"""
from fastapi import FastAPI

from app.api.router import router
from app.core.config import settings


def build_app() -> FastAPI:
    """
    The router mounted the way `app/main.py` mounts it.

    Read through the OpenAPI schema rather than `app.routes`: this FastAPI
    resolves included routers lazily, so the route objects are still
    placeholders until the schema is generated. The schema is also what any
    client generator would see, which is the contract being pinned.
    """
    app = FastAPI()
    app.include_router(router, prefix=settings.api_prefix)
    return app


SCHEMA = build_app().openapi()
# Dicts preserve insertion order, so this is registration order.
PATHS = list(SCHEMA["paths"])
ROUTES = {
    (method.upper(), path)
    for path, operations in SCHEMA["paths"].items()
    for method in operations
}


def test_the_prefix_is_v2():
    # Every path asserted below is written out in full, so this is the one
    # place the prefix itself is pinned.
    assert settings.api_prefix == "/v2"


def has(method: str, path: str) -> bool:
    return (method, path) in ROUTES


class TestDocumentRoutes:
    def test_listing(self):
        assert has("GET", "/v2/metadata")

    def test_detail_is_a_separate_path_from_update(self):
        # Reading one document is /detail; /metadata/{id} itself is write-only.
        assert has("GET", "/v2/metadata/{document}/detail")
        assert has("PUT", "/v2/metadata/{document}")
        assert has("DELETE", "/v2/metadata/{document}")
        assert not has("GET", "/v2/metadata/{document}")

    def test_rename_has_no_route_of_its_own(self):
        # Renaming is the PUT above with a {"name": ...} body. The frontend
        # used to post to /rename, which never existed.
        assert not any(path.endswith("/rename") for _, path in ROUTES)

    def test_star_is_a_put(self):
        assert has("PUT", "/v2/metadata/{document_id}/star")
        assert not has("GET", "/v2/metadata/{document_id}/star")

    def test_archiving_is_a_post_keyed_by_name(self):
        assert has("POST", "/v2/metadata/archive/{file_name}")
        assert has("POST", "/v2/metadata/un-archive/{file_name}")
        assert has("GET", "/v2/metadata/archive/list")
        # It is not a GET, however convenient that would be from a link.
        assert not has("GET", "/v2/metadata/archive/{file_name}")

    def test_download_and_preview(self):
        assert has("GET", "/v2/file/{file_id}/download")
        assert has("GET", "/v2/preview/{document}")

    def test_move(self):
        assert has("POST", "/v2/{document_id}/move")

    def test_upload(self):
        assert has("POST", "/v2/upload")
        assert has("POST", "/v2/upload-folder-bulk")


class TestTrashRoutes:
    def test_trash(self):
        assert has("GET", "/v2/trash")
        assert has("DELETE", "/v2/trash")
        # Keyed by id, not name. `name` is deliberately not unique, so the old
        # name-keyed routes acted on whichever trashed row was found first.
        assert has("DELETE", "/v2/trash/{doc_id}")
        assert has("POST", "/v2/restore/{doc_id}")
        assert not has("DELETE", "/v2/trash/{file_name}")
        assert not has("POST", "/v2/restore/{file}")


class TestDoubledPrefixes:
    def test_folders_are_mounted_twice_on_purpose(self):
        assert has("POST", "/v2/folders/folders/")
        assert has("GET", "/v2/folders/folders/{parent_id}/children")

    def test_office_is_mounted_twice_on_purpose(self):
        assert has("POST", "/v2/office/office/config")
        assert has("POST", "/v2/office/office/callback/{doc_id}")


class TestCatchAllOrdering:
    def test_the_catch_all_delete_is_registered_last(self):
        """
        `DELETE /v2/{file_name:path}` swallows anything registered after it.

        app/api/router.py includes documents_router last for exactly this
        reason; reordering the includes would break every other DELETE.
        """
        catch_all = PATHS.index("/v2/{file_name}")
        for specific in [
            "/v2/sharing/share/{share_id}",
            "/v2/metadata/{document}",
            # `/trash/{doc_id}` is int-typed, so a non-numeric segment falls
            # through to the catch-all — but a numeric one must reach the trash
            # route, which requires it to be registered first.
            "/v2/trash/{doc_id}",
            "/v2/restore/{doc_id}",
        ]:
            assert PATHS.index(specific) < catch_all, specific


class TestNoRoutesTheFrontendInvents:
    def test_there_is_no_approvals_api(self):
        # The Approvals page posts to /docs/{id}/approve. Nothing serves it, so
        # the buttons are disabled — see src/pages/Approvals.tsx.
        assert not any("approve" in path or "reject" in path for _, path in ROUTES)

    def test_there_is_no_documents_prefix(self):
        # DocumentRow used to call /api/documents/{id}/archive.
        assert not any(path.startswith("/v2/documents/") for _, path in ROUTES)
