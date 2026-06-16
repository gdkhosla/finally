# FinAlly — AI Trading Workstation

A visually stunning, AI-powered trading workstation that streams live market data, simulates portfolio trading, and integrates an LLM chat assistant that can analyze positions and execute trades through natural language. It looks and feels like a modern Bloomberg terminal with an AI copilot.

Built entirely by coding agents as the capstone project for an agentic AI coding course. Agents collaborate through shared documents in [`planning/`](planning/).

## Features

- **Live price streaming** via Server-Sent Events (SSE), with green/red flash animations on each tick
- **Simulated portfolio** — $10,000 virtual cash, market orders only, instant fills, no fees
- **Sparkline mini-charts** accumulated on the frontend from the SSE stream since page load
- **Portfolio visualizations** — treemap heatmap (sized by weight, colored by P&L), total-value P&L chart, positions table
- **AI chat assistant** — analyzes holdings, suggests trades, and auto-executes trades and watchlist changes
- **Watchlist management** — add/remove tickers manually or via the AI
- **Dark terminal aesthetic** — data-dense, desktop-first layout

## Architecture

A single Docker container serves everything on **port 8000**:

```
┌─────────────────────────────────────────────┐
│  Docker Container (port 8000)               │
│  FastAPI (Python / uv)                      │
│  ├── /api/*          REST endpoints         │
│  ├── /api/stream/*   SSE streaming          │
│  └── /*              Static Next.js export  │
│  SQLite (volume-mounted at db/finally.db)   │
│  Background task: market data sim / poller  │
└─────────────────────────────────────────────┘
```

| Layer | Choice |
|---|---|
| Frontend | Next.js + TypeScript, static export (`output: 'export'`), Tailwind CSS |
| Backend | FastAPI (Python), managed with `uv` |
| Database | SQLite, single file, lazily initialized and seeded |
| Real-time | Server-Sent Events (one-way server→client push) |
| AI | OpenAI `gpt-5-nano` with structured outputs for trade execution |
| Market data | Built-in GBM simulator (default), or Massive/Polygon.io API (optional) |

See [`planning/PLAN.md`](planning/PLAN.md) for the full specification and the rationale behind each decision.

## Build Status

This project is under active development by coding agents.

- ✅ **Market data subsystem** — GBM simulator, Massive API client, thread-safe price cache, and SSE streaming are complete. See [`planning/MARKET_DATA_SUMMARY.md`](planning/MARKET_DATA_SUMMARY.md).
- 🚧 **Backend API** — portfolio, watchlist, trade, and chat endpoints
- 🚧 **Frontend** — Next.js trading terminal UI
- 🚧 **Docker, start/stop scripts, and E2E tests**

## Quick Start (Docker)

Once the container build is complete:

```bash
# Configure
cp .env.example .env
# Add your OPENAI_API_KEY to .env

# Build and run
docker build -t finally .
docker run -v finally-data:/app/db -p 8000:8000 --env-file .env finally

# Open http://localhost:8000
```

The SQLite database persists across restarts via the `finally-data` volume.

## Local Development

### Backend

```bash
cd backend
uv sync --extra dev                          # Install deps incl. test/lint tools
uv run market_data_demo.py                   # Live terminal dashboard (simulated prices)
uv run --extra dev pytest -v                 # Run tests
uv run --extra dev pytest --cov=app          # With coverage
uv run --extra dev ruff check app/ tests/    # Lint
```

The market data subsystem lives in `backend/app/market/`. Default tickers and per-ticker
GBM parameters are in `backend/app/market/seed_prices.py`. See
[`backend/CLAUDE.md`](backend/CLAUDE.md) for the developer API guide.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | OpenAI API key for the AI chat assistant (`gpt-5-nano`) |
| `MASSIVE_API_KEY` | No | Massive (Polygon.io) key for real market data; omit to use the built-in simulator |
| `LLM_MOCK` | No | Set to `true` for deterministic mock LLM responses (E2E testing) |

The backend reads `.env` from the project root.

## Project Structure

```
finally/
├── frontend/    # Next.js static export (TypeScript, Tailwind)
├── backend/     # FastAPI uv project
│   └── app/
│       └── market/   # Market data: simulator, Massive client, cache, SSE
├── planning/    # Project documentation and agent contracts (PLAN.md is authoritative)
├── scripts/     # Start/stop helpers (mac/linux + Windows PowerShell)
├── test/        # Playwright E2E tests + docker-compose.test.yml
└── db/          # SQLite volume mount target (runtime; finally.db is gitignored)
```

## Default Seed Data

- One user profile with `$10,000.00` cash
- Watchlist: AAPL, GOOGL, MSFT, AMZN, TSLA, NVDA, META, JPM, V, NFLX

## License

See [LICENSE](LICENSE).
