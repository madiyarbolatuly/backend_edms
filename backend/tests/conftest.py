import os
import uuid
import pytest
import httpx

BASE_URL = os.getenv("EDMS_BASE_URL", "http://localhost:8000").rstrip("/")
PRIMARY_PREFIX = os.getenv("EDMS_API_PREFIX", "/v2")
ALT_PREFIX = os.getenv("EDMS_API_ALT_PREFIX", "")  # например "/api/v2" если нужно
TENANT_ID = int(os.getenv("EDMS_TENANT_ID", "1"))
DEPARTMENT_ID = int(os.getenv("EDMS_DEPARTMENT_ID", "1"))

def _join(*parts: str) -> str:
    return "/".join(p.strip("/") for p in parts if p is not None)

def _path(path: str, use_alt: bool = False) -> str:
    prefix = ALT_PREFIX if use_alt and ALT_PREFIX else PRIMARY_PREFIX
    return f"{BASE_URL}/{_join(prefix, path)}"

def _try_both(client: httpx.Client, method: str, path: str, **kwargs) -> httpx.Response:
    # сначала основной префикс
    url1 = _path(path, use_alt=False)
    resp = client.request(method, url1, **kwargs)
    if resp.status_code != 404 or not ALT_PREFIX:
        return resp
    # если 404 и задан альтернативный префикс — пробуем его
    url2 = _path(path, use_alt=True)
    return client.request(method, url2, **kwargs)

@pytest.fixture(scope="session")
def http():
    # общий sync клиент
    with httpx.Client(timeout=60) as client:
        yield client

@pytest.fixture(scope="session")
def auth_headers(http: httpx.Client):
    """
    Возвращает заголовки Authorization. Если есть EDMS_USERNAME/PASSWORD —
    логинится ими. Иначе — регистрирует уникального admin-пользователя и логинится.
    """
    username = os.getenv("EDMS_USERNAME")
    password = os.getenv("EDMS_PASSWORD")

    if not username or not password:
        # создаём уникального админа
        suffix = uuid.uuid4().hex[:8]
        username = f"tester_{suffix}"
        password = f"Pass_{suffix}!"
        email = f"{username}@example.com"
        signup_body = {
            "tenant_id": TENANT_ID,
            "department_id": DEPARTMENT_ID,
            "username": username,
            "email": email,
            "password": password,
            "role": "admin",
        }
        r = _try_both(http, "POST", "u/signup", json=signup_body)
        assert r.status_code in (201, 200), f"signup failed: {r.status_code} {r.text}"

    # login (form-url-encoded)
    form = {
        "grant_type": "password",
        "username": username,
        "password": password,
        "scope": "",
        "client_id": "",
        "client_secret": "",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = _try_both(http, "POST", "u/login", data=form, headers=headers)
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    token = r.json().get("access_token")
    assert token, f"no access_token in response: {r.text}"
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture
def unique_names():
    """
    Генератор уникальных имён на прогон: файл, папка.
    """
    s = uuid.uuid4().hex[:8]
    return {
        "file": f"test_{s}.txt",
        "folder": f"folder_{s}",
        "file2": f"move_{s}.txt",
    }

# Вспомогалки, доступные тестам:
@pytest.fixture
def api_helpers(http: httpx.Client, auth_headers):
    class API:
        def post(self, path: str, **kw):  # json / files / params
            kw.setdefault("headers", {}).update(auth_headers)
            return _try_both(http, "POST", path, **kw)

        def get(self, path: str, **kw):
            kw.setdefault("headers", {}).update(auth_headers)
            return _try_both(http, "GET", path, **kw)

        def delete(self, path: str, **kw):
            kw.setdefault("headers", {}).update(auth_headers)
            return _try_both(http, "DELETE", path, **kw)

        def put(self, path: str, **kw):
            kw.setdefault("headers", {}).update(auth_headers)
            return _try_both(http, "PUT", path, **kw)

        def patch(self, path: str, **kw):
            kw.setdefault("headers", {}).update(auth_headers)
            return _try_both(http, "PATCH", path, **kw)

    return API()
