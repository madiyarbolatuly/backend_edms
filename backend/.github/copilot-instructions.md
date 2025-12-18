## Copilot / AI agent instructions for DocFlow (backend)

Short, actionable guidance to help an AI agent make targeted code changes in this repository.

1) Big picture
- This is a FastAPI service that exposes a v2 API (see `app/core/config.py`: `api_prefix` — default `/v2`).
- Entry point: `app/main.py` — registers lifespan startup (calls `check_tables()`), mounts static files and the frontend, and includes the main router.
- Routers are composed under `app/api/router.py` (top-level router that `include_router`'s per-feature routers). Many feature routers define their own internal paths and are included with small prefixes (e.g. `auth` under `/u`, `folders` under `/folders` — final path becomes `/v2/folders`).
- DB layer uses SQLAlchemy with both synchronous and asynchronous engines: `app/db/models.py` defines `engine`, `async_engine`, `session`, and `async_session` factories.

2) Key files and what they reveal (examples)
- app/main.py — app lifecycle, CORS origins, static mounts (`/files` -> `uploads`), docs urls. Note: `check_tables()` is executed at startup via lifespan.
- app/core/config.py — environment-driven settings; exposes `settings.async_database_url` and `settings.sync_database_url` and `api_prefix`.
- app/api/router.py — how subrouters are mounted; follow the pattern `router.include_router(my_router, prefix="/my")`.
- app/api/dependencies/database.py — `get_async_session()` yields an `AsyncSession` and uses `await session.flush()`; endpoints expect dependency-injected sessions (do not call `session.commit()` directly in dependencies).
- app/db/crud.py and `app/db/tables/` — CRUD patterns: use `sqlalchemy.future.select()`, call `result.scalar_one_or_none()` then raise project helpers like `app.core.exceptions.http_404()`.
- app/core/exceptions.py — standardized helpers (http_400/http_401/http_403/http_404/http_409/http_500). Use these for consistent error responses.
- app/api/routes/onlyoffice.py and app/integrations/onlyoffice.py — OnlyOffice integration example (signing tokens, callback handling, saving new versions).

3) Environment & runtime notes
- Env vars used extensively (see `app/core/config.py`): POSTGRES_USER, POSTGRES_PASSWORD, DATABASE_HOSTNAME, POSTGRES_PORT, POSTGRES_DB, JWT_SECRET_KEY, JWT_REFRESH_SECRET_KEY, ACCESS_TOKEN_EXPIRE_MIN, REFRESH_TOKEN_EXPIRE_MIN, etc.
- DB URLs are constructed by `settings.sync_database_url` and `settings.async_database_url`. Use those when composing connection strings.
- To run locally in dev: ensure required env vars are set, then run: `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000` (module is `app.main:app`).
- Docker/dev: there are multiple docker-compose files at repo root. The common one is `docker-compose.yml` and there are env-specific ones (`docker-compose.prod.yml`, etc.).

4) Project-specific conventions and gotchas
- Router prefixes: many routers define their own internal paths and are included under the top-level router. Be careful — adding a prefix at include time + internal router paths can double prefixes. Inspect `app/api/routes/*` files to find the exact route path.
- DB sessions: endpoints should use the `get_async_session()` dependency (`app/api/dependencies/database.py`). It yields a session and calls `flush()` rather than explicit commit. Follow this pattern when adding/altering CRUD.
- Error handling: prefer raising helpers from `app/core/exceptions.py` rather than constructing raw HTTPException objects.
- Table creation: `check_tables()` in `app/db/models.py` runs `metadata.create_all(engine)` on startup. For structural migrations prefer Alembic (alembic.ini and migrations/ exist).
- Uploads/static: uploads are mounted at `/files` and created on startup from `settings.upload_dir`. Tests or code that write files should use `settings.UPLOADS_DIR`.

5) Integration points to watch
- OnlyOffice: `app/api/routes/onlyoffice.py` calls utilities in `app/integrations/onlyoffice.py` and `app/services/versioning.py`. The callback endpoint fetches edited content via a publicly reachable URL — keep public URL construction (`BACKEND_PUBLIC_URL`) correct.
- External services: SMTP (email), Document Server, and Postgres are configured by env vars. Mock or stub these in tests; some code expects `BACKEND_PUBLIC_URL` to be reachable by external services.

6) How to make safe changes (small checklist for PRs)
- Run unit tests: `pytest` (project has `pytest.ini`).
- Start the app locally with `uvicorn app.main:app --reload` and validate `/docs` (or configured docs_url) and a few endpoints under `/v2`.
- If changing DB models, create an Alembic migration instead of relying on `metadata.create_all` for production schema changes.
- Add/modify routes by updating the feature file in `app/api/routes/...` and the top-level `app/api/router.py` if a new router must be included.

7) Quick examples
- Where an endpoint gets a DB session:
  - see `app/api/dependencies/database.py` -> use `Depends(get_async_session)` in route signature.
- Raising a not-found error in CRUD:
  - use `from app.core.exceptions import http_404` and `raise http_404(msg=f"User with ID {user_id} not found.")` (see `app/db/crud.py`).

If anything here is unclear or you want the agent to follow stricter conventions (PR templates, lint rules, or testing gating), tell me what to add and I will iterate.
