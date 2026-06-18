# FinAlly — Team Coordination Contract

This is the shared contract for the agent team building FinAlly. Read this first.
The authoritative product spec is `planning/PLAN.md`. The completed market-data subsystem
is described in `planning/MARKET_DATA_SUMMARY.md` — **build on it, do not modify it.**

Today's date: 2026-06-18. Stack is fixed by PLAN.md (FastAPI + uv backend, Next.js TS
static-export frontend, SQLite, SSE, OpenAI `gpt-5-nano`, single Docker container on port 8000).

---

## Team & File Ownership

Each agent owns a disjoint set of paths. **Do not edit files outside your ownership.**
If you need a change in someone else's area, note it in `planning/TEAM_NOTES.md`.

| Agent | Owns | Depends on |
|-------|------|-----------|
| **Database Engineer** | `backend/app/db/` (schema, init, seed, repository functions) | market models (read-only) |
| **Backend Engineer** | `backend/app/services/`, `backend/app/api/` (portfolio, watchlist, health routes), `backend/app/main.py`, `backend/app/config.py` | `app.db`, `app.market` |
| **LLM Engineer** | `backend/app/llm/`, `backend/app/api/chat.py` | `app.db`, `app.services.portfolio` |
| **Frontend Engineer** | `frontend/` (entire tree) | the documented `/api/*` contract only |
| **DevOps Engineer** | `Dockerfile`, `.dockerignore`, `scripts/`, `.env.example`, `db/.gitkeep`, `.gitignore` (additions only), `README.md` | knows final dir structure |
| **Integration Tester** | `test/` (Playwright + `docker-compose.test.yml`) | runs the whole app |

Each agent also writes its own **unit tests** under its area (`backend/tests/...`,
`frontend/` test files). Tests must pass before you report done.

---

## Backend module interfaces (the contract that enables parallel work)

### `app.db` — owned by Database Engineer, imported by Backend & LLM

```python
from app.db import init_db, get_conn  # init_db() lazy-creates+seeds; get_conn() yields sqlite3 conn

# Repository functions (all take user_id: str = "default"):
from app.db import repo
repo.get_profile()                  -> dict  {id, cash_balance, created_at}
repo.set_cash(new_balance: float)   -> None
repo.list_watchlist()               -> list[str]               # tickers
repo.watchlist_has(ticker)          -> bool
repo.add_watchlist(ticker)          -> None                    # idempotent (UNIQUE)
repo.remove_watchlist(ticker)       -> None
repo.get_position(ticker)           -> dict | None  {ticker, quantity, avg_cost}
repo.list_positions()               -> list[dict]
repo.upsert_position(ticker, quantity, avg_cost) -> None
repo.delete_position(ticker)        -> None                    # used when qty hits 0
repo.record_trade(ticker, side, quantity, price) -> dict       # returns the trade row
repo.list_trades(limit=None)        -> list[dict]
repo.record_snapshot(total_value)   -> None
repo.list_snapshots(limit=500)      -> list[dict]              # downsampled/limited; newest-bounded
repo.list_messages(limit=20)        -> list[dict]              # chronological order
repo.add_message(role, content, actions=None) -> dict          # actions = JSON-serializable | None
```

Use plain `sqlite3` (stdlib), `check_same_thread=False`, short-lived connection per call, row
factory returning dicts. Keep it simple — no ORM. Money stored full-precision; quantities rounded
to 4 dp **by the caller** (services), not the repo. Lazy init: `init_db()` creates tables + seeds
the default profile and 10-ticker watchlist if empty. Schema exactly per PLAN.md Section 7.

### `app.services.portfolio` — owned by Backend Engineer, imported by LLM

```python
from app.services.portfolio import execute_trade, get_portfolio

execute_trade(ticker: str, side: str, quantity: float) -> dict
# Validates (qty>0; buy: cash>=cost; sell: own>=qty). Auto-adds ticker to watchlist+market
# source if missing (so a fill price exists). Updates position (avg-cost on buy; delete row on
# full sell), cash, records trade, records a snapshot. Returns:
#   {"ok": True,  "trade": {...}, "fill_price": float}
#   {"ok": False, "error": "human-readable reason"}      # never raises on validation failure
# Quantity rounded to 4 dp here. Fill price = price_cache.get_price(ticker).

get_portfolio() -> dict
# {cash_balance, positions:[{ticker,quantity,avg_cost,current_price,unrealized_pnl,pct_change}],
#  total_value, unrealized_pnl}   — authoritative P&L per PLAN.md Section 7 "Numeric Precision".
```

### `app.market` — DONE, read-only. Import the singletons created in `main.py`.

Backend Engineer creates the singletons in `main.py`:
```python
from app.market import PriceCache, create_market_data_source, create_stream_router
price_cache = PriceCache()
market_source = create_market_data_source(price_cache)
```
Expose them for import by services (e.g. `from app.main import price_cache, market_source`, or a
small `app/state.py` module to avoid circular imports — **Backend Engineer's choice; document it
in TEAM_NOTES.md so LLM/services import the right path**). `market_source.add_ticker/remove_ticker`
are async; call them from async route handlers.

---

## HTTP API contract (frozen — frontend builds against this)

All under same origin. Shapes per PLAN.md Section 8. Summary:

- `GET  /api/health` -> `{"status":"ok"}`
- `GET  /api/stream/prices` -> SSE (DONE, see MARKET_DATA_SUMMARY.md; full price map per event)
- `GET  /api/portfolio` -> `get_portfolio()` shape above
- `POST /api/portfolio/trade` body `{ticker, quantity, side}` -> `{ok, trade?, fill_price?, error?}`; 200 on success, 400 on validation failure with `{detail}` or `{ok:false,error}`
- `GET  /api/portfolio/history` -> `{"snapshots":[{total_value, recorded_at}, ...]}` (limited/downsampled)
- `GET  /api/watchlist` -> `{"tickers":[{ticker, price, previous_price, change, change_percent, direction}]}` (price from cache; may be null until first tick)
- `POST /api/watchlist` body `{ticker}` -> 200 `{ok:true}` / 400 on dup
- `DELETE /api/watchlist/{ticker}` -> 200 `{ok:true}` / 400 if open position exists
- `POST /api/chat` body `{message}` -> `{message, trades:[...executed with results], watchlist_changes:[...], error?}`

Watchlist↔market coupling and trade auto-add live in the route/service handlers per
MARKET_DATA_SUMMARY.md "Watchlist ↔ Market Source Coupling".

---

## LLM contract

`gpt-5-nano` via OpenAI SDK, Structured Outputs, schema `{message, trades[], watchlist_changes[]}`
per PLAN.md Section 9. `OPENAI_API_KEY` from `.env`. When `LLM_MOCK=true`, return deterministic
responses keyed off the input message (same schema) so e2e tests can assert inline actions — see
PLAN.md Section 9 "LLM Mock Mode". Auto-execute trades via `app.services.portfolio.execute_trade`
and watchlist changes via the same path the watchlist route uses; include per-action results in
the response. Load last 20 messages for context.

---

## Conventions

- Backend: `uv run ...` always (never bare python/pip). Tests: `uv run pytest`. No emojis in code/logs.
- Be simple; don't overengineer or program defensively. Short modules/functions, clear names.
- Frontend: Next.js (TS) with `output: 'export'`, Tailwind dark theme, colors per PLAN.md
  (`#0d1117` bg, accent `#ecad0a`, blue `#209dd7`, purple `#753991`). Build must produce a static
  export servable by FastAPI. Live header total value computed from SSE, not polling.
- Commit nothing unless the orchestrator says so. Report status concisely when done: what you built,
  test results (real output), and anything that blocks another agent.

## Cross-agent notes
Append blockers / interface clarifications to `planning/TEAM_NOTES.md` (create if missing).
