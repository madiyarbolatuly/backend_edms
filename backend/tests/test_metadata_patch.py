"""
Patching document metadata.

`DocumentMetadataPatch` accepts `tags`, `categories` and `access_to`; the
`documents` table has none of those columns. They went straight into
`update().values()`, which raised CompileError — and `_execute_update` wrapped
it as `http_409("Ошибка при обновлении документа: <name>")`. So renaming a
document while also sending tags reported a *name conflict*, and the actual
cause never appeared anywhere.
"""
import pytest

from app.db.repositories.documents.documents_metadata import MetadataRepository


class TestWritableChanges:
    def test_columns_the_table_has_are_kept(self):
        assert MetadataRepository._writable_changes({"name": "a.pdf"}) == {"name": "a.pdf"}

    def test_fields_the_table_does_not_have_are_dropped(self):
        changes = {"name": "a.pdf", "tags": ["x"], "categories": ["y"], "access_to": ["u"]}

        assert MetadataRepository._writable_changes(changes) == {"name": "a.pdf"}

    def test_a_patch_of_only_unknown_fields_is_empty(self):
        # The caller must then skip the UPDATE entirely — `values({})` is itself
        # an error.
        assert MetadataRepository._writable_changes({"tags": ["x"]}) == {}

    @pytest.mark.parametrize(
        "column",
        ["id", "tenant_id", "department_id", "owner_id", "document_number",
         "created_at", "file_path", "file_hash"],
    )
    def test_identity_and_storage_columns_are_not_patchable(self, column):
        # A client must not be able to move a document to another tenant, or
        # point it at another file, through a metadata patch.
        assert MetadataRepository._writable_changes({column: "x"}) == {}

    def test_parent_id_is_patchable_but_moving_is_not_this_endpoints_job(self):
        # `parent_id` is a real column so it survives the filter; relocating a
        # document properly goes through `move_document`, which also moves the
        # file. Recorded so the difference is deliberate rather than incidental.
        assert MetadataRepository._writable_changes({"parent_id": 5}) == {"parent_id": 5}


class TestPatch:
    @pytest.mark.asyncio
    async def test_renaming_alongside_tags_renames_instead_of_erroring(
        self, repo, owner, make_document
    ):
        doc = await make_document("old.pdf")

        result = await repo.patch(
            document=doc.id,
            document_patch={"name": "new.pdf", "tags": ["смета"]},
            owner=owner,
            user_repo=None,
            is_owner=True,
        )

        assert result.name == "new.pdf"

    @pytest.mark.asyncio
    async def test_a_patch_of_only_unknown_fields_is_a_no_op(
        self, repo, owner, make_document
    ):
        doc = await make_document("keep.pdf")

        result = await repo.patch(
            document=doc.id,
            document_patch={"tags": ["смета"]},
            owner=owner,
            user_repo=None,
            is_owner=True,
        )

        assert result.name == "keep.pdf"

    @pytest.mark.asyncio
    async def test_another_tenants_document_cannot_be_patched(
        self, repo, owner, make_document
    ):
        doc = await make_document("theirs.pdf", tenant_id=999)

        with pytest.raises(Exception):
            await repo.patch(
                document=doc.id,
                document_patch={"name": "mine.pdf"},
                owner=owner,
                user_repo=None,
                is_owner=True,
            )
