# app/integrations/onlyoffice.py
import hashlib
import logging
import os
import time
from urllib.parse import urlparse

import jwt

logger = logging.getLogger(__name__)

DOCUMENT_SERVER_PUBLIC = os.getenv("DOCUMENT_SERVER_PUBLIC", "http://localhost:8085")
BACKEND_PUBLIC_URL = os.getenv("BACKEND_PUBLIC_URL", "http://localhost:8000")

DOC_TYPE_BY_EXT = {
    "docx": "word",
    "xlsx": "cell",
    "pptx": "slide",
}


class OnlyOfficeNotConfigured(RuntimeError):
    """Raised when a token operation is attempted with no shared secret set."""


def _secret() -> str:
    """
    The secret shared with Document Server.

    This used to default to the literal "supersecret_please_change", which is
    almost certainly what any deployment following `.env.template` is running —
    and anyone who knows it can forge an editor config or a save callback.
    There is now no default: signing and verification fail closed instead.

    Deliberately *not* raised at import. `app/main.py` and `app/api/router.py`
    both import this router unconditionally, so an import-time raise would take
    down the whole API for deployments that do not use the editor at all.
    """
    secret = os.getenv("ONLYOFFICE_JWT_SECRET", "").strip()
    if not secret:
        raise OnlyOfficeNotConfigured(
            "ONLYOFFICE_JWT_SECRET is not set. The editor is disabled until it is, "
            "and its value must match Document Server's JWT_SECRET."
        )
    return secret


def is_configured() -> bool:
    return bool(os.getenv("ONLYOFFICE_JWT_SECRET", "").strip())


def build_doc_key(doc_id: str, version_hint: int = 1) -> str:
    raw = f"{doc_id}:{version_hint}:{int(time.time() // (60*10))}"  # rotates every 10 min
    return hashlib.sha256(raw.encode()).hexdigest()


def sign_token(payload: dict) -> str:
    return jwt.encode(payload, _secret(), algorithm="HS256")


def verify_token(token: str) -> dict:
    """
    Decode a token Document Server signed.

    `algorithms` is pinned: without it, PyJWT will honour whatever `alg` the
    token itself claims, including `none`, which makes the signature optional
    for anyone who asks.
    """
    return jwt.decode(token, _secret(), algorithms=["HS256"])


def is_document_server_url(url: str) -> bool:
    """
    Whether `url` points at the configured Document Server.

    The callback hands us a URL and we fetch it, so without this an attacker who
    can reach the endpoint can make the server request anything it can route to
    — including cloud metadata endpoints — and then write the response over a
    document.
    """
    try:
        candidate = urlparse(url)
        expected = urlparse(DOCUMENT_SERVER_PUBLIC)
    except ValueError:
        return False

    if candidate.scheme not in {"http", "https"}:
        return False
    if not candidate.hostname:
        return False

    # Host must match; the port is allowed to differ because Document Server
    # advertises its own internal address in the callback.
    return candidate.hostname == expected.hostname
