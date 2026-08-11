# Backend tests

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest
```

No Postgres and no running services are needed: the suite creates the
`documents` table in an in-memory SQLite database, one per test.

## Why SQLite

Everything these tests exercise — recursive CTEs, `lower()` ordering, `ILIKE`,
`OFFSET`/`LIMIT` — behaves identically on SQLite and Postgres, and the one
Postgres-only thing in the schema (the `text_pattern_ops` index) is a dialect
keyword SQLAlchemy skips elsewhere. The trade is that `pytest` works on a
checkout with nothing running.

The one place the two differ and it matters is case folding: SQLite's `lower()`
only handles ASCII, so a Cyrillic case-insensitive search would fail here while
passing in production. `test_is_case_insensitive` deliberately uses ASCII rather
than assert something the database under test cannot do.

## Layout

| File | Covers |
| --- | --- |
| `conftest.py` | Env bootstrapping, an async SQLite session, a document factory |
| `test_doc_list.py` | Ordering, paging, scoping, search and the recursive walk |
| `test_document_indexes.py` | The indexes the listing queries depend on |
| `test_routes.py` | The routing table the frontend is written against |

## The environment

`app/core/config.py` reads Postgres settings at import time, so `conftest.py`
loads `app/.env` and fills in defaults *before* importing anything under `app.`.
Nothing ever connects to those settings — they only have to parse.

## Keeping the two contract tests in step

`test_routes.py` pins the API's paths; `edms-frontend/src/config/api.test.ts`
pins the URLs the frontend builds against them. A route that moves should break
both. The frontend file documents the one-liner that regenerates its copy of the
table from the OpenAPI schema.
