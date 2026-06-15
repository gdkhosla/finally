# FinAlly — AI Trading Workstation

## Project Specification

## 1. Vision

FinAlly (Finance Ally) is a visually stunning AI-powered trading workstation that streams live market data, lets users trade a simulated portfolio, and integrates an LLM chat assistant that can analyze positions and execute trades on the user's behalf. It looks and feels like a modern Bloomberg terminal with an AI copilot.

This is the capstone project for an agentic AI coding course. It is built entirely by Coding Agents demonstrating how orchestrated AI agents can produce a production-quality full-stack application. Agents interact through files in `planning/`.

## 2. User Experience

### First Launch

The user runs a single Docker command (or a provided start script). A browser opens to `http://localhost:8000`. No login, no signup. They immediately see:

- A watchlist of 10 default tickers with live-updating prices in a grid
- $10,000 in virtual cash
- A dark, data-rich trading terminal aesthetic
- An AI chat panel ready to assist

### What the User Can Do

- **Watch prices stream** — prices flash green (uptick) or red (downtick) with subtle CSS animations that fade
- **View sparkline mini-charts** — price action beside each ticker in the watchlist, accumulated on the frontend from the SSE stream since page load (sparklines fill in progressively)
- **Click a ticker** to see a larger detailed chart in the main chart area
- **Buy and sell shares** — market orders only, instant fill at current price, no fees, no confirmation dialog
- **Monitor their portfolio** — a heatmap (treemap) showing positions sized by weight and colored by P&L, plus a P&L chart tracking total portfolio value over time
- **View a positions table** — ticker, quantity, average cost, current price, unrealized P&L, % change
- **Chat with the AI assistant** — ask about their portfolio, get analysis, and have the AI execute trades and manage the watchlist through natural language
- **Manage the watchlist** — add/remove tickers manually or via the AI chat

### Visual Design

- **Dark theme**: backgrounds around `#0d1117` or `#1a1a2e`, muted gray borders, no pure black
- **Price flash animations**: brief green/red background highlight on price change, fading over ~500ms via CSS transitions
- **Connection status indicator**: a small colored dot (green = connected, yellow = reconnecting, red = disconnected) visible in the header
- **Professional, data-dense layout**: inspired by Bloomberg/trading terminals — every pixel earns its place
- **Responsive but desktop-first**: optimized for wide screens, functional on tablet

### Color Scheme
- Accent Yellow: `#ecad0a`
- Blue Primary: `#209dd7`
- Purple Secondary: `#753991` (submit buttons)

## 3. Architecture Overview

### Single Container, Single Port

```
┌─────────────────────────────────────────────────┐
│  Docker Container (port 8000)                   │
│                                                 │
│  FastAPI (Python/uv)                            │
│  ├── /api/*          REST endpoints             │
│  ├── /api/stream/*   SSE streaming              │
│  └── /*              Static file serving         │
│                      (Next.js export)            │
│                                                 │
│  SQLite database (volume-mounted)               │
│  Background task: market data polling/sim        │
└─────────────────────────────────────────────────┘
```

- **Frontend**: Next.js with TypeScript, built as a static export (`output: 'export'`), served by FastAPI as static files
- **Backend**: FastAPI (Python), managed as a `uv` project
- **Database**: SQLite, single file at `db/finally.db`, volume-mounted for persistence
- **Real-time data**: Server-Sent Events (SSE) — simpler than WebSockets, one-way server→client push, works everywhere
- **AI integration**: OpenAI platform integration using gpt-5-nano model, with structured outputs for trade execution
- **Market data**: Environment-variable driven — simulator by default, real data via Massive API if key provided

### Why These Choices

| Decision | Rationale |
|---|---|
| SSE over WebSockets | One-way push is all we need; simpler, no bidirectional complexity, universal browser support |
| Static Next.js export | Single origin, no CORS issues, one port, one container, simple deployment |
| SQLite over Postgres | No auth = no multi-user = no need for a database server; self-contained, zero config |
| Single Docker container | Students run one command; no docker-compose for production, no service orchestration |
| uv for Python | Fast, modern Python project management; reproducible lockfile; what students should learn |
| Market orders only | Eliminates order book, limit order logic, partial fills — dramatically simpler portfolio math |

---

## 4. Directory Structure

```
finally/
├── frontend/                 # Next.js TypeScript project (static export)
├── backend/                  # FastAPI uv project (Python)
│   └── db/                   # Schema definitions, seed data, migration logic
├── planning/                 # Project-wide documentation for agents
│   ├── PLAN.md               # This document
│   └── ...                   # Additional agent reference docs
├── scripts/
│   ├── start_mac.sh          # Launch Docker container (macOS/Linux)
│   ├── stop_mac.sh           # Stop Docker container (macOS/Linux)
│   ├── start_windows.ps1     # Launch Docker container (Windows PowerShell)
│   └── stop_windows.ps1      # Stop Docker container (Windows PowerShell)
├── test/                     # Playwright E2E tests + docker-compose.test.yml
├── db/                       # Volume mount target (SQLite file lives here at runtime)
│   └── .gitkeep              # Directory exists in repo; finally.db is gitignored
├── Dockerfile                # Multi-stage build (Node → Python)
├── .env                      # Environment variables (gitignored, .env.example committed)
└── .gitignore
```

### Key Boundaries

- **`frontend/`** is a self-contained Next.js project. It knows nothing about Python. It talks to the backend via `/api/*` endpoints and `/api/stream/*` SSE endpoints. Internal structure is up to the Frontend Engineer agent.
- **`backend/`** is a self-contained uv project with its own `pyproject.toml`. It owns all server logic including database initialization, schema, seed data, API routes, SSE streaming, market data, and LLM integration. Internal structure is up to the Backend/Market Data agents.
- **`backend/db/`** contains schema SQL definitions and seed logic. The backend lazily initializes the database on first request — creating tables and seeding default data if the SQLite file doesn't exist or is empty.
- **`db/`** at the top level is the runtime volume mount point. The SQLite file (`db/finally.db`) is created here by the backend and persists across container restarts via Docker volume.
- **`planning/`** contains project-wide documentation, including this plan. All agents reference files here as the shared contract.
- **`test/`** contains Playwright E2E tests and supporting infrastructure (e.g., `docker-compose.test.yml`). Unit tests live within `frontend/` and `backend/` respectively, following each framework's conventions.
- **`scripts/`** contains start/stop scripts that wrap Docker commands.

---

## 5. Environment Variables

```bash
# Required: OpenAI API key for LLM chat functionality (gpt-5-nano)
OPENAI_API_KEY=your-openai-api-key-here

# Optional: Massive (Polygon.io) API key for real market data
# If not set, the built-in market simulator is used (recommended for most users)
MASSIVE_API_KEY=

# Optional: Set to "true" for deterministic mock LLM responses (testing)
LLM_MOCK=false
```

### Behavior

- If `MASSIVE_API_KEY` is set and non-empty → backend uses Massive REST API for market data
- If `MASSIVE_API_KEY` is absent or empty → backend uses the built-in market simulator
- If `LLM_MOCK=true` → backend returns deterministic mock LLM responses (for E2E tests)
- The backend reads `.env` from the project root (mounted into the container or read via docker `--env-file`)

---

## 6. Market Data

### Two Implementations, One Interface

Both the simulator and the Massive client implement the same abstract interface. The backend selects which to use based on the environment variable. All downstream code (SSE streaming, price cache, frontend) is agnostic to the source.

### Simulator (Default)

- Generates prices using geometric Brownian motion (GBM) with configurable drift and volatility per ticker
- Updates at ~500ms intervals
- Correlated moves across tickers (e.g., tech stocks move together)
- Occasional random "events" — sudden 2-5% moves on a ticker for drama
- Starts from realistic seed prices. The illustrative values here (e.g., AAPL ~$190, GOOGL ~$175) are not authoritative — the actual seed prices and per-ticker GBM params live in `backend/app/market/seed_prices.py`
- Runs as an in-process background task — no external dependencies

### Massive API (Optional)

- REST API polling (not WebSocket) — simpler, works on all tiers
- Polls for the union of all watched tickers on a configurable interval
- Free tier (5 calls/min): poll every 15 seconds
- Paid tiers: poll every 2-15 seconds depending on tier
- Parses REST response into the same format as the simulator

### Shared Price Cache

- A single background task (simulator or Massive poller) writes to an in-memory price cache
- The cache holds the latest price, previous price, and timestamp for each ticker
- SSE streams read from this cache and push updates to connected clients
- This architecture supports future multi-user scenarios without changes to the data layer

### SSE Streaming

- Endpoint: `GET /api/stream/prices`
- Long-lived SSE connection; client uses native `EventSource` API
- The stream emits on change, polled at ~500ms: the server checks the price cache every ~500ms and pushes an event only for tickers whose price actually changed (version-based change detection). In the single-user model the tracked set is equivalent to the user's watchlist
- Each SSE event contains ticker, price, previous price, timestamp, and change direction
- Client handles reconnection automatically (EventSource has built-in retry)

---

## 7. Database

### SQLite with Lazy Initialization

The backend checks for the SQLite database on startup (or first request). If the file doesn't exist or tables are missing, it creates the schema and seeds default data. This means:

- No separate migration step
- No manual database setup
- Fresh Docker volumes start with a clean, seeded database automatically

### Schema

All tables include a `user_id` column defaulting to `"default"`. This is hardcoded for now (single-user) but enables future multi-user support without schema migration.

**users_profile** — User state (cash balance)
- `id` TEXT PRIMARY KEY (default: `"default"`)
- `cash_balance` REAL (default: `10000.0`)
- `created_at` TEXT (ISO timestamp)

**watchlist** — Tickers the user is watching
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `added_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**positions** — Current holdings (one row per ticker per user). When a sell brings `quantity` to 0, the row is deleted (no zero-quantity rows), so the positions table and heatmap never render empty entries.
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `quantity` REAL (fractional shares supported)
- `avg_cost` REAL
- `updated_at` TEXT (ISO timestamp)
- UNIQUE constraint on `(user_id, ticker)`

**trades** — Trade history (append-only log)
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `ticker` TEXT
- `side` TEXT (`"buy"` or `"sell"`)
- `quantity` REAL (fractional shares supported)
- `price` REAL
- `executed_at` TEXT (ISO timestamp)

**portfolio_snapshots** — Portfolio value over time (for P&L chart). Recorded every 30 seconds by a background task, and immediately after each trade execution. The table grows unbounded; rather than a retention job, `GET /api/portfolio/history` downsamples/limits what it returns (see Section 8).
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `total_value` REAL
- `recorded_at` TEXT (ISO timestamp)

**chat_messages** — Conversation history with LLM
- `id` TEXT PRIMARY KEY (UUID)
- `user_id` TEXT (default: `"default"`)
- `role` TEXT (`"user"` or `"assistant"`)
- `content` TEXT
- `actions` TEXT (JSON — trades executed, watchlist changes made; null for user messages)
- `created_at` TEXT (ISO timestamp)

### Default Seed Data

- One user profile: `id="default"`, `cash_balance=10000.0`
- Ten watchlist entries: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

### Numeric Precision (single source of truth)

To keep backend and frontend P&L math identical:

- **Storage:** full float precision at rest (SQLite, `PriceUpdate`). Rounding is presentation-only.
- **Money display:** 2 decimals (prices, cash, P&L, total value).
- **Share quantity:** rounded to **4 decimals** on trade entry, so `quantity × price` is reproducible.
- **Authoritative P&L:** the backend computes and returns all P&L / total-value numbers from `/api/portfolio`. The frontend re-derives only the *live* total between fetches using the identical formula: `total_value = cash + Σ(quantity × live_price)`, with `unrealized_pnl = Σ(quantity × (live_price − avg_cost))`.

---

## 8. API Endpoints

### Market Data
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stream/prices` | SSE stream of live price updates |

### Portfolio
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/portfolio` | Current positions, cash balance, total value, unrealized P&L |
| POST | `/api/portfolio/trade` | Execute a trade: `{ticker, quantity, side}` |
| GET | `/api/portfolio/history` | Portfolio value snapshots over time (for P&L chart) |

**Trade auto-adds the ticker to the watchlist.** If the traded `ticker` is not already on the watchlist, executing the trade adds it (which also starts the market source tracking it, per the watchlist rules below). This guarantees a live price exists for the fill and applies to both manual trades and AI-initiated trades.

**`/api/portfolio/history` limits its payload.** Because `portfolio_snapshots` grows unbounded, this endpoint downsamples/limits what it returns (e.g., the last N points or last 24h) rather than returning the full table.

### Watchlist
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/watchlist` | Current watchlist tickers with latest prices |
| POST | `/api/watchlist` | Add a ticker: `{ticker}` |
| DELETE | `/api/watchlist/{ticker}` | Remove a ticker |

**Watchlist ↔ market-source coupling lives in the watchlist route handler.** Adding a ticker calls `source.add_ticker(...)`; removing one calls `source.remove_ticker(...)`, keeping DB state and the live price set in sync. Rules:
- The last ticker **may** be removed (an empty watchlist is allowed).
- A ticker with an **open position may not** be removed (reject with an error); the user must close the position first.
- **Interaction with trade auto-add:** trading a ticker auto-adds it to the watchlist (see Portfolio above). Combined with the rule above, this means a ticker acquired via a trade stays pinned to the watchlist until its position is fully sold — only then can it be removed. The trade handler and watchlist handler must both honor this coupling.

### Chat
| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat` | Send a message, receive complete JSON response (message + executed actions) |

### System
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health check (for Docker/deployment) |

---

## 9. LLM Integration

When writing code to make calls to LLMs, use OpenAI platform with `gpt-5-nano` model. Structured Outputs should be used to interpret the results.

There is an OPENAI_API_KEY in the .env file in the project root.

### How It Works

When the user sends a chat message, the backend:

1. Loads the user's current portfolio context (cash, positions with P&L, watchlist with live prices, total portfolio value)
2. Loads recent conversation history from the `chat_messages` table (the last 20 messages)
3. Constructs a prompt with a system message, portfolio context, conversation history, and the user's new message
4. Calls the LLM, requesting structured output
5. Parses the complete structured JSON response
6. Auto-executes any trades or watchlist changes specified in the response
7. Stores the message and executed actions in `chat_messages`
8. Returns the complete JSON response to the frontend (no token-by-token streaming)

### Structured Output Schema

The LLM is instructed to respond with JSON matching this schema:

```json
{
  "message": "Your conversational response to the user",
  "trades": [
    {"ticker": "AAPL", "side": "buy", "quantity": 10}
  ],
  "watchlist_changes": [
    {"ticker": "PYPL", "action": "add"}
  ]
}
```

- `message` (required): The conversational text shown to the user
- `trades` (optional): Array of trades to auto-execute. Each trade goes through the same validation as manual trades (sufficient cash for buys, sufficient shares for sells)
- `watchlist_changes` (optional): Array of watchlist modifications

### Auto-Execution

Trades specified by the LLM execute automatically — no confirmation dialog. This is a deliberate design choice:
- It's a simulated environment with fake money, so the stakes are zero
- It creates an impressive, fluid demo experience
- It demonstrates agentic AI capabilities — the core theme of the course

If a trade fails validation (e.g., insufficient cash), the error is included in the chat response so the LLM can inform the user.

### System Prompt Guidance

The LLM should be prompted as "FinAlly, an AI trading assistant" with instructions to:
- Analyze portfolio composition, risk concentration, and P&L
- Suggest trades with reasoning
- Execute trades when the user asks or agrees
- Manage the watchlist proactively
- Be concise and data-driven in responses
- Always respond with valid structured JSON

### LLM Mock Mode

When `LLM_MOCK=true`, the backend returns deterministic mock responses instead of calling OpenAI. The mock returns the same Structured Output Schema defined above (the `{message, trades, watchlist_changes}` shape), keyed off the input message so E2E tests can assert inline trade/watchlist actions deterministically. This enables:
- Fast, free, reproducible E2E tests
- Development without an API key
- CI/CD pipelines

---

## 10. Frontend Design

### Layout

The frontend is a single-page application with a dense, terminal-inspired layout. The specific component architecture and layout system is up to the Frontend Engineer, but the UI should include these elements:

- **Watchlist panel** — grid/table of watched tickers with: ticker symbol, current price (flashing green/red on change), change % since open/load (the baseline is the first price seen for that ticker since the process/page started — there is no real "daily close"), and a sparkline mini-chart (accumulated from SSE since page load)
- **Main chart area** — larger chart for the currently selected ticker, with at minimum price over time. Clicking a ticker in the watchlist selects it here.
- **Portfolio heatmap** — treemap visualization where each rectangle is a position, sized by portfolio weight, colored by P&L (green = profit, red = loss)
- **P&L chart** — line chart showing total portfolio value over time, using data from `portfolio_snapshots`
- **Positions table** — tabular view of all positions: ticker, quantity, avg cost, current price, unrealized P&L, % change (vs. avg cost)
- **Trade bar** — simple input area: ticker field, quantity field, buy button, sell button. Market orders, instant fill.
- **AI chat panel** — docked/collapsible sidebar. Message input, scrolling conversation history, loading indicator while waiting for LLM response. Trade executions and watchlist changes shown inline as confirmations.
- **Header** — portfolio total value, connection status indicator, cash balance. The total value updates live, computed on the frontend from the SSE price stream × held quantities (plus cash) — no polling loop against `/api/portfolio`

### Technical Notes

- Use `EventSource` for SSE connection to `/api/stream/prices`
- Canvas-based charting library preferred (Lightweight Charts or Recharts) for performance
- Price flash effect: on receiving a new price, briefly apply a CSS class with background color transition, then remove it
- All API calls go to the same origin (`/api/*`) — no CORS configuration needed
- Tailwind CSS for styling with a custom dark theme

---

## 11. Docker & Deployment

### Multi-Stage Dockerfile

```
Stage 1: Node 20 slim
  - Copy frontend/
  - npm install && npm run build (produces static export)

Stage 2: Python 3.12 slim
  - Install uv
  - Copy backend/
  - uv sync (install Python dependencies from lockfile)
  - Copy frontend build output into a static/ directory
  - Expose port 8000
  - CMD: uvicorn serving FastAPI app
```

FastAPI serves the static frontend files and all API routes on port 8000.

### Docker Volume

The SQLite database persists via a named Docker volume:

```bash
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally
```

The `db/` directory in the project root maps to `/app/db` in the container. The backend writes `finally.db` to this path.

### Start/Stop Scripts

**`scripts/start_mac.sh`** (macOS/Linux):
- Builds the Docker image if not already built (or if `--build` flag passed)
- Runs the container with the volume mount, port mapping, and `.env` file
- Prints the URL to access the app
- Optionally opens the browser

**`scripts/stop_mac.sh`** (macOS/Linux):
- Stops and removes the running container
- Does NOT remove the volume (data persists)

**`scripts/start_windows.ps1`** / **`scripts/stop_windows.ps1`**: PowerShell equivalents for Windows.

All scripts should be idempotent — safe to run multiple times.

### Optional Cloud Deployment

The container is designed to deploy to AWS App Runner, Render, or any container platform. A Terraform configuration for App Runner may be provided in a `deploy/` directory as a stretch goal, but is not part of the core build.

---

## 12. Testing Strategy

### Unit Tests (within `frontend/` and `backend/`)

**Backend (pytest)**:
- Market data: simulator generates valid prices, GBM math is correct, Massive API response parsing works, both implementations conform to the abstract interface
- Portfolio: trade execution logic, P&L calculations, edge cases (selling more than owned, buying with insufficient cash, selling at a loss)
- LLM: structured output parsing handles all valid schemas, graceful handling of malformed responses, trade validation within chat flow
- API routes: correct status codes, response shapes, error handling

**Frontend (React Testing Library or similar)**:
- Component rendering with mock data
- Price flash animation triggers correctly on price changes
- Watchlist CRUD operations
- Portfolio display calculations
- Chat message rendering and loading state

### E2E Tests (in `test/`)

**Infrastructure**: A separate `docker-compose.test.yml` in `test/` that spins up the app container plus a Playwright container. This keeps browser dependencies out of the production image.

**Environment**: Tests run with `LLM_MOCK=true` by default for speed and determinism.

**Key Scenarios**:
- Fresh start: default watchlist appears, $10k balance shown, prices are streaming
- Add and remove a ticker from the watchlist
- Buy shares: cash decreases, position appears, portfolio updates
- Sell shares: cash increases, position updates or disappears
- Portfolio visualization: heatmap renders with correct colors, P&L chart has data points
- AI chat (mocked): send a message, receive a response, trade execution appears inline
- SSE resilience: disconnect and verify reconnection

---

## 13. Review — Questions, Clarifications & Simplifications

Added by doc-review. Grouped by impact. Items marked **[blocker]** should be resolved before the relevant component is built.

**Status:** All items resolved and folded into the sections above. Item 11 was dropped. (Item 15 → see "Numeric Precision" in Section 7.)

### Contradictions to resolve

1. **OpenAI vs OpenRouter [blocker].** Section 5 comments the key as `# Required: OpenRouter API key`, but Section 9 and the env var name (`OPENAI_API_KEY`) say "OpenAI platform with `gpt-5-nano`." These are different providers with different base URLs and SDKs. Which is authoritative? Recommend picking one and fixing the stray comment. (Note: a `cerebras` skill exists in this repo that wires LiteLLM + OpenRouter — if the course intends OpenRouter, the code path and key name should match.)
Answer: Will use OPENAI gpt-5-nano, please fix this doc accordingly.

2. **SSE cadence vs change detection.** Section 6 says the server "pushes price updates ... at a regular cadence (~500ms)," but the completed market data subsystem (`MARKET_DATA_SUMMARY.md`) uses *version-based change detection* — it only emits when a price actually changes. These describe different behaviors. Recommend updating the PLAN to state: "the stream emits on change, polled at ~500ms," so the frontend contract is unambiguous.
Answer: Will go ahead with your recommendation

### Ambiguities the frontend/backend need pinned down

3. **Where does "daily change %" come from? [blocker]** The watchlist and positions table both show a daily/% change, but the simulator has no concept of a previous close — and `PriceUpdate.previous_price` is the *last tick*, not the day's open. Without a defined baseline, "change %" is just per-tick noise. Options: (a) treat the seed price as the day's reference, (b) snapshot the first price seen at process start, (c) drop "daily" and label it "change since open/load." Pick one and document it.
Answer: Lets go with option (c)

4. **Can you trade a ticker that isn't in the watchlist?** `POST /api/portfolio/trade` takes a `ticker`. If it's not being tracked by the market source, `cache.get_price()` returns `None` and the fill price is undefined. Decide: does trading auto-add the ticker to the watchlist + market source, or is it rejected with an error? The AI flow has the same question (it can buy `PYPL` while only adding it via a separate `watchlist_changes` entry).
Answer: Trading should auto-add the ticket to the watchlist

5. **Watchlist ↔ market-source sync.** Adding/removing a watchlist row must call `source.add_ticker/remove_ticker` (per the summary's API). Where does that coupling live — in the watchlist route handler? Worth stating explicitly so DB state and the live price set can't drift apart. Also: can the last ticker be removed (empty watchlist), and can a ticker with an open position be removed from the watchlist?
Answer: let the coupling live in watchlist route handler. Last ticket can be removed, don't remove a ticker with open position.

6. **Header "total value updating live" — pull or push?** Total portfolio value changes every tick. Is the header recomputed on the frontend from SSE prices × held quw antities, or does it poll `/api/portfolio`? Recommend frontend-side computation from the SSE stream to avoid a polling loop; document it so it isn't built twice.
Answer: will go ahead with recommendation.

7. **Chat history window.** Section 9 step 2 loads "recent conversation history" — define the limit (e.g., last N messages or a token budget). Unbounded history will eventually break the `gpt-5-nano` context window.
Answer: last 20 messages

8. **`LLM_MOCK=true` response contract.** E2E tests assert "trade execution appears inline," which requires the mock to return deterministic `trades`/`watchlist_changes`. Specify the mock's exact output (e.g., keyed off input text) so tests and the mock don't drift.
Answer: lets use the structured output mentioned at line 301

### Simplification opportunities

9. **Drop `docker-compose.yml` for production.** Section 4 lists a root `docker-compose.yml` as an "optional convenience wrapper," while Section 11 deliberately uses a single `docker run`. Two ways to launch the same container is extra surface to maintain. The start scripts already wrap `docker run`; recommend removing the root compose file and keeping only `test/docker-compose.test.yml`.
Answer: lets apply this suggestion.

10. **`portfolio_snapshots` growth.** A snapshot every 30s = ~2,880 rows/day, unbounded. For a single-user demo this is harmless for a long while, but the P&L chart query and payload grow forever. Cheapest fix: have `GET /api/portfolio/history` downsample/limit (e.g., last N points or last 24h) rather than adding a retention job.
Answer: lets apply this suggestion

12. **`avg_cost` on full sell.** When `quantity` hits 0, the spec says the position row "disappears." Confirm sells delete the row (vs. leaving a zero-qty row), so the positions table and heatmap don't render empty rectangles.
Answer: when the quantity hits 0, lets remove the row

### Minor / nits

13. Section 5 header says "OpenRouter API key for LLM chat" — same contradiction as #1; fix together.
Answer: fix it
14. Seed prices in the PLAN ("AAPL ~$190, GOOGL ~$175") are illustrative — the authoritative values now live in `seed_prices.py`. Consider a one-line pointer so the PLAN isn't mistaken for the source of truth.
Answer: fix it as your recommendation
15. Confirm fractional-share rounding/display precision (prices and quantities) is defined in one place to keep frontend and backend P&L math identical.
Answer: please elaborate and lets chat about it
