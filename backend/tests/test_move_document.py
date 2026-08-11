"""
Moving a document or folder.

The defect these exist for was silent data loss. `move_document` looked for the
source at `upload_dir/<tenant>/<department>/<file_path>` while uploads write to
`upload_dir/<file_path>` — `settings.upload_dir` already *is* the
tenant/department root. So `old_abs.exists()` was always false, the physical
move was skipped, and `file_path` was rewritten regardless. The row then pointed
at nothing, the bytes stayed at a path no longer recorded anywhere, and no error
was raised.

`test_the_file_moves_on_disk` fails against the pre-fix code.
"""
import pytest

from app.core.config import settings
from pathlib import Path

pytestmark = pytest.mark.asyncio


def write(root: Path, rel: str, content: bytes = b"data") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


async def folder(make_document, name, **kw):
    return await make_document(
        name, file_type="folder", size=None, file_path=kw.pop("file_path", name), **kw
    )


class TestTheFileFollowsTheRow:
    async def test_the_file_moves_on_disk(self, repo, owner, make_document, uploads):
        dest = await folder(make_document, "Архив")
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        source = write(uploads, "смета.xlsx")

        await repo.move_document(document_id=doc.id, new_parent_id=dest.id, user=owner)

        assert not source.exists()
        assert (uploads / "Архив/смета.xlsx").read_bytes() == b"data"

    async def test_the_row_and_the_file_agree_afterwards(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        write(uploads, "смета.xlsx")

        moved = await repo.move_document(
            document_id=doc.id, new_parent_id=dest.id, user=owner
        )

        assert moved.file_path == "Архив/смета.xlsx"
        assert (Path(settings.upload_dir) / moved.file_path).is_file()

    async def test_moving_to_the_root(self, repo, owner, make_document, uploads):
        src = await folder(make_document, "Проект")
        doc = await make_document(
            "смета.xlsx", parent_id=src.id, file_path="Проект/смета.xlsx"
        )
        write(uploads, "Проект/смета.xlsx")

        moved = await repo.move_document(
            document_id=doc.id, new_parent_id=None, user=owner
        )

        assert moved.file_path == "смета.xlsx"
        assert moved.parent_id is None
        assert (uploads / "смета.xlsx").is_file()


class TestMissingSource:
    async def test_a_file_with_no_bytes_is_refused(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        doc = await make_document("призрак.xlsx", file_path="призрак.xlsx")
        # Deliberately not written to disk.

        with pytest.raises(FileNotFoundError):
            await repo.move_document(
                document_id=doc.id, new_parent_id=dest.id, user=owner
            )

    async def test_a_refused_move_leaves_the_row_alone(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        doc = await make_document("призрак.xlsx", file_path="призрак.xlsx")

        with pytest.raises(FileNotFoundError):
            await repo.move_document(
                document_id=doc.id, new_parent_id=dest.id, user=owner
            )

        # The whole point: the path is not rewritten to somewhere with no file.
        assert doc.file_path == "призрак.xlsx"

    async def test_a_folder_with_no_directory_still_moves(
        self, repo, owner, make_document, uploads
    ):
        # `create_folder` only inserts a row, so an empty folder legitimately
        # has nothing on disk.
        dest = await folder(make_document, "Архив")
        doc = await folder(make_document, "Пустая")

        moved = await repo.move_document(
            document_id=doc.id, new_parent_id=dest.id, user=owner
        )

        assert moved.file_path == "Архив/Пустая"


class TestDescendants:
    async def test_descendant_paths_are_re_anchored(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        src = await folder(make_document, "Проект")
        sub = await folder(
            make_document, "Раздел", parent_id=src.id, file_path="Проект/Раздел"
        )
        leaf = await make_document(
            "f.pdf", parent_id=sub.id, file_path="Проект/Раздел/f.pdf"
        )
        write(uploads, "Проект/Раздел/f.pdf")

        await repo.move_document(document_id=src.id, new_parent_id=dest.id, user=owner)

        assert sub.file_path == "Архив/Проект/Раздел"
        assert leaf.file_path == "Архив/Проект/Раздел/f.pdf"
        assert (uploads / "Архив/Проект/Раздел/f.pdf").is_file()

    async def test_a_sibling_sharing_a_name_prefix_is_untouched(
        self, repo, owner, make_document, uploads
    ):
        """`Проект` must not drag `Проект2024` along with it."""
        dest = await folder(make_document, "Архив")
        src = await folder(make_document, "Проект")
        await make_document("mine.pdf", parent_id=src.id, file_path="Проект/mine.pdf")
        write(uploads, "Проект/mine.pdf")

        sibling = await folder(make_document, "Проект2024")
        theirs = await make_document(
            "theirs.pdf", parent_id=sibling.id, file_path="Проект2024/theirs.pdf"
        )
        write(uploads, "Проект2024/theirs.pdf")

        await repo.move_document(document_id=src.id, new_parent_id=dest.id, user=owner)

        assert theirs.file_path == "Проект2024/theirs.pdf"
        assert (uploads / "Проект2024/theirs.pdf").is_file()

    async def test_a_folder_name_with_an_underscore_does_not_match_its_neighbour(
        self, repo, owner, make_document, uploads
    ):
        """The old descendant query used an unescaped LIKE, where `_` is a wildcard."""
        dest = await folder(make_document, "Архив")
        src = await folder(make_document, "2024_Q1")
        write(uploads, "2024_Q1/mine.pdf")
        await make_document("mine.pdf", parent_id=src.id, file_path="2024_Q1/mine.pdf")

        neighbour = await folder(make_document, "2024XQ1")
        theirs = await make_document(
            "theirs.pdf", parent_id=neighbour.id, file_path="2024XQ1/theirs.pdf"
        )

        await repo.move_document(document_id=src.id, new_parent_id=dest.id, user=owner)

        assert theirs.file_path == "2024XQ1/theirs.pdf"


class TestRejections:
    async def test_moving_into_your_own_descendant_is_refused(
        self, repo, owner, make_document, uploads
    ):
        src = await folder(make_document, "Проект")
        sub = await folder(
            make_document, "Раздел", parent_id=src.id, file_path="Проект/Раздел"
        )

        with pytest.raises(ValueError, match="подпапку"):
            await repo.move_document(
                document_id=src.id, new_parent_id=sub.id, user=owner
            )

    async def test_moving_into_itself_is_refused(
        self, repo, owner, make_document, uploads
    ):
        src = await folder(make_document, "Проект")

        with pytest.raises(ValueError):
            await repo.move_document(
                document_id=src.id, new_parent_id=src.id, user=owner
            )

    async def test_a_name_collision_at_the_destination_is_refused(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        write(uploads, "смета.xlsx")
        # Something is already sitting where this would land.
        write(uploads, "Архив/смета.xlsx", b"existing")

        with pytest.raises(ValueError, match="уже существует"):
            await repo.move_document(
                document_id=doc.id, new_parent_id=dest.id, user=owner
            )

        # And the incumbent is intact.
        assert (uploads / "Архив/смета.xlsx").read_bytes() == b"existing"

    async def test_a_missing_destination_is_refused(
        self, repo, owner, make_document, uploads
    ):
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        write(uploads, "смета.xlsx")

        with pytest.raises(ValueError, match="Целевая папка"):
            await repo.move_document(
                document_id=doc.id, new_parent_id=987654, user=owner
            )

    async def test_a_file_cannot_be_used_as_a_destination(
        self, repo, owner, make_document, uploads
    ):
        target = await make_document("не-папка.pdf", file_path="не-папка.pdf")
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        write(uploads, "смета.xlsx")

        with pytest.raises(ValueError, match="Целевая папка"):
            await repo.move_document(
                document_id=doc.id, new_parent_id=target.id, user=owner
            )


class TestScoping:
    async def test_another_tenants_document_cannot_be_moved(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        theirs = await make_document(
            "их.xlsx", tenant_id=999, department_id=999, file_path="их.xlsx"
        )

        with pytest.raises(ValueError, match="не найден"):
            await repo.move_document(
                document_id=theirs.id, new_parent_id=dest.id, user=owner
            )

    async def test_another_tenants_folder_cannot_be_a_destination(
        self, repo, owner, make_document, uploads
    ):
        theirs = await folder(
            make_document, "Их архив", tenant_id=999, department_id=999
        )
        doc = await make_document("смета.xlsx", file_path="смета.xlsx")
        write(uploads, "смета.xlsx")

        with pytest.raises(ValueError, match="Целевая папка"):
            await repo.move_document(
                document_id=doc.id, new_parent_id=theirs.id, user=owner
            )

    async def test_a_non_owner_without_admin_is_refused(
        self, repo, owner, make_document, uploads
    ):
        dest = await folder(make_document, "Архив")
        doc = await make_document(
            "чужой.xlsx", owner_id="someone-else", file_path="чужой.xlsx"
        )
        write(uploads, "чужой.xlsx")

        with pytest.raises(ValueError, match="Нет прав"):
            await repo.move_document(
                document_id=doc.id, new_parent_id=dest.id, user=owner
            )
