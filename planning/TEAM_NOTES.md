# FinAlly — Team Notes

Cross-agent interface clarifications and blockers. Append; do not delete prior entries.

---

## DevOps Engineer — 2026-06-18

### Static files path

The Dockerfile copies the Next.js static export (`frontend/out/`) into `/app/static` inside the container. The **Backend Engineer must mount this directory** in `app/main.py` using FastAPI's `StaticFiles` with SPA fallback so that all non-`/api` routes serve `index.html`. Example:

```python
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import pathlib

STATIC_DIR = pathlib.Path("/app/static")

# Mount static assets (JS, CSS, images, etc.)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static-assets")

# SPA catch-all: serve index.html for any unmatched route
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    return FileResponse(STATIC_DIR / "index.html")
```

The `/api` prefix routes registered before this catch-all will take precedence correctly.

### Environment variable for DB path

The container sets `FINALLY_DB_PATH=/app/db/finally.db`. The Backend/Database Engineer should read `os.environ.get("FINALLY_DB_PATH", "db/finally.db")` so it works both inside Docker and in local development (where `db/finally.db` is relative to the project root or backend dir).

### No root docker-compose.yml

Per PLAN.md item 9, there is no root `docker-compose.yml`. Only `test/docker-compose.test.yml` (owned by the Integration Tester) should exist.

### uv sync flags

`uv sync --frozen --no-dev` is used in the Dockerfile to install only production dependencies from the lockfile. The `--no-dev` flag requires that dev dependencies (pytest, ruff, etc.) be listed under `[dependency-groups]` or `[tool.uv.dev-dependencies]` in `pyproject.toml`, not under `[project.dependencies]`. The Database/Backend Engineers should ensure pytest and test tooling are in a dev group so the production image stays lean.

---

## LLM Engineer — 2026-06-18

### Files created

- `backend/app/llm/schema.py` — Pydantic models: `LLMResponse`, `TradeAction`, `WatchlistChange`
- `backend/app/llm/mock.py` — deterministic mock responses keyed off message text
- `backend/app/llm/client.py` — async OpenAI gpt-5-nano client with structured outputs (uses `client.beta.chat.completions.parse`)
- `backend/app/llm/__init__.py` — public surface
- `backend/app/api/chat.py` — `POST /api/chat` route; `router` is the FastAPI `APIRouter`
- `backend/tests/llm/test_schema.py`, `test_mock.py`, `test_chat.py` — unit tests (14 passed)

### Registering the chat router in main.py

The **Backend Engineer** must include the chat router in `app/main.py`:

```python
from app.api.chat import router as chat_router
app.include_router(chat_router)
```

### LLM_MOCK keying rules (for Integration Tester)

Mock mode is active when env var `LLM_MOCK=true`. Responses are keyed by substring match on the **lowercased** input message, checked in priority order:

| Message contains | trades | watchlist_changes |
|---|---|---|
| `"buy"` | `[{ticker:"AAPL", side:"buy", quantity:1}]` | `[]` |
| `"sell"` | `[{ticker:"AAPL", side:"sell", quantity:1}]` | `[]` |
| `"add"` | `[]` | `[{ticker:"TSLA", action:"add"}]` |
| `"remove"` | `[]` | `[{ticker:"TSLA", action:"remove"}]` |
| (anything else) | `[]` | `[]` |

Priority: `buy > sell > add > remove > plain`. All responses include a non-empty `message` string.

### openai dependency

Added `openai>=1.0` to `[project.dependencies]` in `backend/pyproject.toml`. Dev deps (pytest, pytest-asyncio, httpx) were moved to `[dependency-groups] dev` by `uv lock` automatically.

---

## Backend Engineer — 2026-06-18

### Singleton import path (for LLM / services)

The shared market singletons live in **`app/state.py`**:

```python
from app.state import price_cache, market_source
```

Services and routes import from here (not from `app.main`) to avoid circular imports. `market_source` is unstarted; `app/main.py` owns `start()`/`stop()` in the lifespan.

### execute_trade is ASYNC

`from app.services.portfolio import execute_trade, get_portfolio` — `execute_trade(ticker, side, quantity)` is `async def` (it `await`s `market_source.add_ticker` for auto-add). The chat handler must `await execute_trade(...)`. `get_portfolio()` is sync. Watchlist service `app.services.watchlist.add_ticker_to_watchlist` / `remove_ticker_from_watchlist` are also `async`.

### Files created

- `app/state.py`, `app/config.py`
- `app/services/portfolio.py`, `app/services/watchlist.py`
- `app/api/health.py`, `app/api/portfolio.py`, `app/api/watchlist.py`
- `app/main.py` (lifespan: init_db, start market source, 30s snapshot loop; includes stream/health/portfolio/watchlist routers; chat router included via guarded import; StaticFiles SPA mount guarded for local dev via `FINALLY_STATIC_DIR`, default `/app/static`)
- `tests/services/*`, `tests/api/test_routes.py`

### pyproject

`pytest`, `pytest-asyncio`, `httpx` are in `[dependency-groups] dev`; runtime deps are fastapi, uvicorn[standard], numpy, massive, openai. `uv sync --frozen --no-dev` excludes test tooling (verified).

### ACTION for LLM Engineer — flaky `tests/llm/test_chat.py` DB fixture

`tests/llm/test_chat.py` `mock_db` fixture sets `FINALLY_DB_PATH` env only. But `app/db/connection.py` reads `DB_PATH` **at import time** (module global), so the env var is ignored once the module is imported. The chat tests pass in isolation (they fall back to the real default `db/finally.db`) but ERROR in the full suite with `sqlite3.OperationalError: unable to open database file`. Fix: monkeypatch the attribute too, exactly like `tests/db/test_db.py` and `tests/services/*` do:

```python
import app.db.connection as conn_module
monkeypatch.setattr(conn_module, "DB_PATH", db_path)
```

After that one-line fix all suites pass together. This file is LLM-owned so I did not edit it.

---

## Orchestrator — 2026-06-18 (integration fixes)

Two root-cause bugs fixed while reconciling the full backend suite (152 passed):

1. **`backend/app/db/connection.py` default DB path** used `parents[4]` which resolved to
   `Projects/db/finally.db` (one level above the repo). Corrected to `parents[3]` = repo root
   `finally/db/finally.db`. Also made `get_conn()` resolve `FINALLY_DB_PATH` at call time (not at
   import) so the documented env override is authoritative whenever set. `DB_PATH` module attr
   retained for tests that monkeypatch it.
2. **`backend/tests/llm/test_chat.py`** `mock_services` patched `app.api.chat.os.environ.get`
   globally, which clobbered ALL env lookups (including `FINALLY_DB_PATH`). Removed — `LLM_MOCK`
   is already set by the autouse `set_llm_mock_env` fixture, so the global patch was redundant
   and harmful.

Full suite now: `cd backend && uv run pytest -q` -> 152 passed.

---

## Orchestrator — 2026-06-18 (Docker build fix + full verification)

**Bug (Integration Tester found):** Docker `npm ci` failed — `frontend/package-lock.json` out of
sync (`EUSAGE`, Missing `@emnapi/runtime`/`@emnapi/core`).

**Root cause:** npm-version resolution mismatch. The `node:20-slim` build image ships npm 10.8.2,
which resolves the `@emnapi/*` transitive deps to `1.11.1`; the lockfile (generated by a newer npm)
didn't contain entries npm 10.8.2 accepts. Regenerating on the Windows host (npm 11.6.1) did NOT
fix it — it pinned `@emnapi/runtime@1.10.0`, still mismatched against the container's npm 10.

**Fix:** regenerated `frontend/package-lock.json` INSIDE `node:20-slim` (npm 10.8.2) via
`npm install --package-lock-only`, so the lockfile matches the actual build environment. Lesson:
generate the lockfile with the same npm the Dockerfile uses (or pin npm in the build stage).

**Verified end-to-end:** `docker build` -> exit 0 (406MB image). Container run with LLM_MOCK=true:
/api/health ok, /api/watchlist streams 10 seeded tickers, /api/portfolio = $10k, and / serves the
FinAlly frontend. Path A (Docker) now works.
