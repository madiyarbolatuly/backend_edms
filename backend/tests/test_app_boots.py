"""
The application imports and serves a routing table.

The bug these exist for: `app.mount("/", StaticFiles(...), name="frontend",
title=settings.title)`. Starlette's `mount()` is `(path, app, name)`, so the
`title=` kwarg raised TypeError at import — but only inside
`if frontend_build.exists()`. No checkout that lacks `app/frontend/dist` could
ever hit it, which is every development machine, and every deployment that
serves the SPA separately. It failed exactly where CLAUDE.md says the app serves
its own frontend build.
"""
import pathlib

import pytest
from fastapi import FastAPI

from app.main import app, mount_frontend


def test_the_app_imports_and_has_routes():
    assert app.openapi()["paths"]


def test_mounting_a_frontend_build_does_not_raise(tmp_path):
    """The production branch, which no test could reach before."""
    build = tmp_path / "dist"
    build.mkdir()
    (build / "index.html").write_text("<!doctype html>", encoding="utf-8")

    application = FastAPI()
    assert mount_frontend(application, build) is True
    assert any(getattr(r, "name", None) == "frontend" for r in application.routes)


def test_no_frontend_build_is_not_an_error(tmp_path):
    application = FastAPI()
    assert mount_frontend(application, tmp_path / "absent") is False
    assert not any(getattr(r, "name", None) == "frontend" for r in application.routes)


def test_the_favicon_route_can_actually_match():
    """
    Registered as "favicon.ico" with no leading slash, it could never match a
    request path — and it sat after the catch-all mount at "/", so even the
    corrected path would have been shadowed.
    """
    paths = [getattr(r, "path", None) for r in app.routes]
    assert "/favicon.ico" in paths

    mounts = [i for i, r in enumerate(app.routes) if getattr(r, "path", None) == "/"]
    if mounts:
        assert paths.index("/favicon.ico") < mounts[0]


@pytest.mark.parametrize(
    "module_name, attribute",
    [
        ("app.api.routes.documents.documents", "http_500"),
        ("app.api.routes.documents.document_organization", "http_400"),
        ("app.api.routes.documents.notify", "http_400"),
    ],
)
def test_error_helpers_are_imported_where_they_are_used(module_name, attribute):
    """
    `http_500` was called in `move_document`'s except block but never imported,
    so a failed move raised NameError and discarded the original cause. Cheap
    insurance against the same typo elsewhere.
    """
    module = __import__(module_name, fromlist=[attribute])
    assert hasattr(module, attribute)


def test_the_uploads_directory_is_served():
    assert any(getattr(r, "name", None) == "files" for r in app.routes)
