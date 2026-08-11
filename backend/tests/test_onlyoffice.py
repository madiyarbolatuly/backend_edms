"""
The OnlyOffice save callback.

`POST /office/callback/{doc_id}` had no authentication and never verified the
JWT Document Server signs it with. Anyone who could reach it could post
`{"status": 2, "url": "http://..."}`; the server fetched that URL — any URL —
and wrote the response body over a document. `doc_id` went straight into a
filesystem path, so `../../` escaped the upload root too.

The SSRF test asserts `httpx` was **never invoked**. Asserting only on the
status code would pass even if the request had already gone out.
"""
import jwt
import pytest

from app.integrations import onlyoffice as integration
from app.services import versioning

SECRET = "test-secret"


@pytest.fixture
def configured(monkeypatch):
    monkeypatch.setenv("ONLYOFFICE_JWT_SECRET", SECRET)
    monkeypatch.setattr(integration, "DOCUMENT_SERVER_PUBLIC", "http://docserver:8085")
    return SECRET


class TestSecretHandling:
    def test_signing_fails_closed_without_a_secret(self, monkeypatch):
        monkeypatch.delenv("ONLYOFFICE_JWT_SECRET", raising=False)

        with pytest.raises(integration.OnlyOfficeNotConfigured):
            integration.sign_token({"a": 1})

    def test_verifying_fails_closed_without_a_secret(self, monkeypatch):
        monkeypatch.delenv("ONLYOFFICE_JWT_SECRET", raising=False)

        with pytest.raises(integration.OnlyOfficeNotConfigured):
            integration.verify_token("whatever")

    def test_a_blank_secret_counts_as_unset(self, monkeypatch):
        monkeypatch.setenv("ONLYOFFICE_JWT_SECRET", "   ")

        assert integration.is_configured() is False
        with pytest.raises(integration.OnlyOfficeNotConfigured):
            integration.sign_token({"a": 1})

    def test_the_secret_comes_only_from_the_environment(self, monkeypatch):
        """
        It used to default to a literal in source, so every deployment that
        followed .env.template shared one key — and anyone holding it could
        forge an editor config or a save callback.
        """
        monkeypatch.setenv("ONLYOFFICE_JWT_SECRET", "from-the-env")
        assert integration._secret() == "from-the-env"

        monkeypatch.delenv("ONLYOFFICE_JWT_SECRET")
        with pytest.raises(integration.OnlyOfficeNotConfigured):
            integration._secret()


class TestTokenVerification:
    def test_a_token_signed_with_the_right_secret_round_trips(self, configured):
        token = integration.sign_token({"status": 2})

        assert integration.verify_token(token)["status"] == 2

    def test_a_token_signed_with_another_secret_is_rejected(self, configured):
        forged = jwt.encode({"status": 2}, "not-the-secret", algorithm="HS256")

        with pytest.raises(jwt.InvalidSignatureError):
            integration.verify_token(forged)

    def test_an_unsigned_token_is_rejected(self, configured):
        """`alg: none` is accepted by PyJWT unless `algorithms` is pinned."""
        unsigned = jwt.encode({"status": 2}, key="", algorithm="none")

        with pytest.raises(jwt.InvalidAlgorithmError):
            integration.verify_token(unsigned)


class TestCallbackUrlAllowlist:
    @pytest.mark.parametrize(
        "url",
        [
            "http://169.254.169.254/latest/meta-data/",   # cloud metadata
            "http://localhost:8000/v2/admin/users",       # the API itself
            "http://127.0.0.1/",
            "http://attacker.example.com/payload",
            "file:///etc/passwd",
            "gopher://docserver:8085/",
            "",
            "not a url",
        ],
    )
    def test_urls_outside_document_server_are_refused(self, configured, url):
        assert integration.is_document_server_url(url) is False

    def test_the_document_server_is_allowed(self, configured):
        assert integration.is_document_server_url(
            "http://docserver:8085/cache/files/out.docx"
        ) is True

    def test_a_different_port_on_the_same_host_is_allowed(self, configured):
        # Document Server advertises its own internal address in the callback.
        assert integration.is_document_server_url("http://docserver:9999/x") is True

    def test_a_host_that_merely_ends_with_the_name_is_refused(self, configured):
        assert integration.is_document_server_url(
            "http://evildocserver:8085/x"
        ) is False


class TestStoragePaths:
    def test_a_path_resolves_under_the_upload_root(self, uploads):
        (uploads / "Проект").mkdir()
        resolved = versioning.resolve_within_storage("Проект/смета.xlsx")

        assert resolved == (uploads / "Проект/смета.xlsx").resolve()

    @pytest.mark.parametrize(
        "path",
        ["../../etc/passwd", "Проект/../../../etc/passwd", "/../../etc/passwd"],
    )
    def test_a_traversal_is_refused(self, uploads, path):
        with pytest.raises(ValueError, match="escapes"):
            versioning.resolve_within_storage(path)

    def test_saves_land_where_the_rest_of_the_app_reads(self, uploads):
        """
        `versioning` defined its own storage root, unset by every .env and every
        compose file — so edits made in the browser were written somewhere the
        app never looks and were effectively discarded. It must follow
        `settings.upload_dir`, which is what `uploads` patches.
        """
        from pathlib import Path

        from app.core.config import settings

        assert versioning.storage_root() == Path(settings.upload_dir) == uploads

    def test_snapshots_are_kept_outside_the_served_upload_root(self, uploads):
        # Under upload_dir they would be served by the /files mount and swept
        # into `documents` rows by the importer.
        assert uploads.resolve() not in versioning.versions_dir().resolve().parents

    def test_saving_snapshots_the_previous_content(self, uploads):
        target = uploads / "смета.xlsx"
        target.write_bytes(b"old")

        versioning.save_new_version(absolute_path=target, doc_id=7, content=b"new")

        assert target.read_bytes() == b"new"
        snapshots = list((versioning.versions_dir() / "7").glob("*.xlsx"))
        assert len(snapshots) == 1
        assert snapshots[0].read_bytes() == b"old"

    def test_a_first_save_has_nothing_to_snapshot(self, uploads):
        target = uploads / "новый.docx"

        versioning.save_new_version(absolute_path=target, doc_id=8, content=b"first")

        assert target.read_bytes() == b"first"


class TestCallbackRoute:
    """The route wiring — that a refused fetch is refused *before* it happens."""

    @pytest.mark.asyncio
    async def test_an_ssrf_url_is_never_fetched(self, configured, monkeypatch, repo):
        import app.api.routes.onlyoffice as module

        called = []

        class ExplodingClient:
            def __init__(self, *a, **kw): ...
            async def __aenter__(self):
                return self
            async def __aexit__(self, *a):
                return False
            async def get(self, url):
                called.append(url)
                raise AssertionError(f"the server fetched {url}")

        monkeypatch.setattr(module.httpx, "AsyncClient", ExplodingClient)

        token = integration.sign_token(
            {"status": 2, "url": "http://169.254.169.254/latest/meta-data/"}
        )

        request = _FakeRequest({"status": 2, "url": "http://169.254.169.254/"}, token)

        with pytest.raises(module.HTTPException) as exc:
            await module.onlyoffice_callback(
                doc_id="1", request=request, ext="docx", title=None, repository=repo
            )

        assert exc.value.status_code == 400
        assert called == []

    @pytest.mark.asyncio
    async def test_a_callback_without_a_token_is_rejected(self, configured, repo):
        import app.api.routes.onlyoffice as module

        request = _FakeRequest({"status": 2, "url": "http://docserver:8085/x"}, None)

        with pytest.raises(module.HTTPException) as exc:
            await module.onlyoffice_callback(
                doc_id="1", request=request, ext="docx", title=None, repository=repo
            )

        assert exc.value.status_code == 401

    @pytest.mark.asyncio
    async def test_a_forged_token_is_rejected(self, configured, repo):
        import app.api.routes.onlyoffice as module

        forged = jwt.encode({"status": 2}, "wrong", algorithm="HS256")
        request = _FakeRequest({"status": 2, "url": "http://docserver:8085/x"}, forged)

        with pytest.raises(module.HTTPException) as exc:
            await module.onlyoffice_callback(
                doc_id="1", request=request, ext="docx", title=None, repository=repo
            )

        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_a_non_numeric_doc_id_is_rejected(self, configured, repo):
        import app.api.routes.onlyoffice as module

        token = integration.sign_token(
            {"status": 2, "url": "http://docserver:8085/x"}
        )
        request = _FakeRequest({"status": 2}, token)

        with pytest.raises(module.HTTPException) as exc:
            await module.onlyoffice_callback(
                doc_id="../../etc/passwd", request=request, ext="docx",
                title=None, repository=repo,
            )

        assert exc.value.status_code == 400


class _FakeRequest:
    def __init__(self, body: dict, token: str | None):
        self._body = body
        self.headers = {"authorization": f"Bearer {token}"} if token else {}

    async def json(self):
        return self._body
