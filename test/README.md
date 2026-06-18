# FinAlly E2E Tests

Playwright end-to-end tests covering the PLAN.md Section 12 key scenarios.

Tests run against a live app instance at `BASE_URL` (default `http://localhost:8000`).
They are deterministic: the app must run with `LLM_MOCK=true` (mock LLM) and the
built-in price simulator (no `MASSIVE_API_KEY`).

## Important: start from a fresh database

The "Fresh start" specs assert clean seed state ($10,000 cash, no positions).
Trade specs mutate cash and positions. Run the suite against a **freshly seeded
DB** (no persisted volume / a new `FINALLY_DB_PATH`). The Docker path below does
this automatically because the container starts without a mounted volume.

## Run path A — Docker (recommended)

```bash
docker compose -f docker-compose.test.yml up --build \
  --abort-on-container-exit --exit-code-from playwright
```

Builds the production image from the repo `Dockerfile`, starts it with
`LLM_MOCK=true` + a dummy `OPENAI_API_KEY`, waits for health, then runs Playwright
(from the `mcr.microsoft.com/playwright` image) against `http://app:8000`.

## Run path B — local app

```bash
# 1. Start the backend serving the prebuilt static export, with a fresh DB:
cd ../backend
FINALLY_STATIC_DIR=../frontend/out \
FINALLY_DB_PATH=/tmp/finally_e2e.db \
LLM_MOCK=true OPENAI_API_KEY=test \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# 2. In another shell, run the tests:
cd ../test
npm ci
npx playwright install chromium
BASE_URL=http://127.0.0.1:8000 npx playwright test
```

(On Windows PowerShell, set env with `$env:NAME = "value"` before the uvicorn call.)
