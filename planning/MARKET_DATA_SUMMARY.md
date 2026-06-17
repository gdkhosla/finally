# Market Data — Summary

The market data subsystem is **complete and approved for integration**. This document summarizes
everything downstream code (portfolio, trades, SSE, frontend) needs to know.

---

## Status

- **91 tests, all passing** after post-review fixes.
- **Verdict:** Production-quality; build on it.

---

## Architecture

```
  ┌──────────────────────┐  writes  ┌──────────────┐  reads
  │ SimulatorDataSource   │ ───────▶ │              │ ◀── GET /api/stream/prices  (SSE)
  │  OR                   │          │  PriceCache  │ ◀── trade fill  (get_price)
  │ MassiveDataSource     │ ───────▶ │  (in-memory) │ ◀── portfolio valuation
  └──────────────────────┘          └──────────────┘
           ▲                               │ version++
     MASSIVE_API_KEY?              monotonic int → SSE change detection
```

**Producer/cache/consumer split.** Sources write into `PriceCache`; all consumers read from the
cache. Neither SSE, trade fills, nor portfolio valuation know which source is active.

---

## File Layout

```
backend/app/market/
├── __init__.py       # public re-exports (only these 5 symbols needed downstream)
├── models.py         # PriceUpdate dataclass
├── cache.py          # PriceCache
├── interface.py      # MarketDataSource ABC
├── seed_prices.py    # authoritative seed prices + GBM params
├── simulator.py      # GBMSimulator (pure math) + SimulatorDataSource (async lifecycle)
├── massive.py        # MassiveDataSource (REST polling)
├── factory.py        # create_market_data_source()
└── stream.py         # SSE router — GET /api/stream/prices
```

---

## Public API

```python
from app.market import (
    PriceCache,
    PriceUpdate,
    MarketDataSource,
    create_market_data_source,
    create_stream_router,
)
```

Everything else is internal.

---

## Key Components

### `PriceUpdate` (immutable dataclass)

The single data shape seen by all consumers — identical from both sources.

| Field / property | Value |
|------------------|-------|
| `ticker` | Symbol |
| `price` | Latest price (rounded to 2 dp on cache write) |
| `previous_price` | Price from prior tick (**not** day's close) |
| `timestamp` | Unix seconds |
| `change` | `price − previous_price` (4 dp, computed property) |
| `change_percent` | % vs `previous_price` (4 dp, computed property) |
| `direction` | `"up"` / `"down"` / `"flat"` (computed property) |
| `to_dict()` | JSON-serializable; used as SSE payload |

> `previous_price` is the last tick. The frontend computes "change since open/load" using the
> first price seen on the current page session — it does **not** treat `previous_price` as a
> daily figure.

### `PriceCache`

Thread-safe in-memory store. One `PriceUpdate` per ticker.

```python
cache.update(ticker, price, timestamp=None)  # bumps version; computes prev/change/direction
cache.get(ticker)       -> PriceUpdate | None
cache.get_price(ticker) -> float | None        # trade fills use this
cache.get_all()         -> dict[str, PriceUpdate]  # SSE snapshots
cache.remove(ticker)                           # also bumps version
cache.version           -> int                 # monotonic; SSE reads this for change detection
```

Uses `threading.Lock` (not `asyncio.Lock`) because `MassiveDataSource` writes from a worker
thread via `asyncio.to_thread`.

### `MarketDataSource` interface

```python
async def start(tickers: list[str]) -> None   # called exactly once at app startup
async def stop() -> None                       # idempotent
async def add_ticker(ticker: str) -> None      # no-op if already tracked
async def remove_ticker(ticker: str) -> None   # removes from cache too; no-op if absent
def get_tickers() -> list[str]
```

### Factory

```python
# factory.py — the ONLY place MASSIVE_API_KEY is read
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

Returns an **unstarted** source; the caller owns `await source.start(tickers)`.

---

## Simulator (default — no API key needed)

**Model:** Geometric Brownian Motion with correlated sectors.

```
S(t+dt) = S(t) × exp( (mu − sigma²/2)·dt  +  sigma·√dt·Z_correlated )
dt = 0.5 / (252 × 6.5 × 3600)  ≈ 8.48e-8   (500 ms as a year-fraction)
```

**Correlation** via Cholesky decomposition on an n×n matrix rebuilt on each add/remove:

| Pair | ρ |
|------|---|
| Same tech sector (AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX) | 0.6 |
| Same finance sector (JPM, V) | 0.5 |
| Cross-sector / unknown | 0.3 |
| TSLA vs anything | 0.3 |

**Random events:** each tick each ticker has 0.1% probability of a ±2–5% shock (for visual drama).

**Seed prices** (`seed_prices.py` — single source of truth):

| Ticker | Seed | σ | µ |
|--------|------|---|---|
| AAPL | $190 | 0.22 | 0.05 |
| GOOGL | $175 | 0.24 | 0.06 |
| MSFT | $420 | 0.20 | 0.07 |
| AMZN | $185 | 0.28 | 0.08 |
| TSLA | $250 | 0.50 | 0.03 |
| NVDA | $870 | 0.40 | 0.10 |
| META | $510 | 0.26 | 0.06 |
| JPM | $200 | 0.17 | 0.05 |
| V | $275 | 0.18 | 0.06 |
| NFLX | $625 | 0.30 | 0.04 |

Unknown tickers get a random seed price in [50, 300] and `DEFAULT_PARAMS` (µ=0.05, σ=0.25).

**Two classes:** `GBMSimulator` (pure sync math, unit-testable in isolation) and
`SimulatorDataSource` (async lifecycle + cache writes, runs every 500 ms).

---

## Massive API (optional — real data)

Activated when `MASSIVE_API_KEY` is set. Polls `GET /v2/snapshot/locale/us/markets/stocks/tickers`
for all watched tickers in one request.

- **Free tier:** 15-min delayed, 5 req/min → poll every 15 s.
- **Paid tiers:** real-time, poll every 2–5 s.
- SDK is **synchronous**; called via `asyncio.to_thread` so the event loop is never blocked.
- `last_trade.timestamp` from the SDK is in **milliseconds** → divide by 1000 for Unix seconds.
- Bad/missing snapshots are skipped per-ticker (never poison the batch).
- Poll errors are logged and swallowed; the background task never crashes on transient 429/401.

---

## SSE Streaming — `GET /api/stream/prices`

```python
# Event format
retry: 1000

data: {"AAPL": {"ticker":"AAPL","price":191.42,"previous_price":191.38,"timestamp":1750000000,"change":0.04,"change_percent":0.0209,"direction":"up"}, ...}
```

- **Emit-on-change:** SSE loop polls `cache.version` every 500 ms; emits only when the version
  changed since the last emission.
- **Full snapshot per event:** the entire price map is sent, not a diff. Client replaces its map
  on every event — safe for reconnection.
- `X-Accel-Buffering: no` header prevents nginx from batching frames.
- `retry: 1000` tells the browser `EventSource` to reconnect after 1 s.

**Frontend usage:**
```typescript
const es = new EventSource("/api/stream/prices");
es.onmessage = (event) => {
  const prices: Record<string, PriceUpdate> = JSON.parse(event.data);
  dispatch(setPrices(prices));
};
es.onerror = () => setConnectionStatus("reconnecting");
```

---

## App Wiring (FastAPI lifespan)

```python
# backend/app/main.py
price_cache   = PriceCache()
market_source = create_market_data_source(price_cache)

@asynccontextmanager
async def lifespan(app: FastAPI):
    tickers = await load_watchlist_tickers()   # 10 default tickers from DB seed
    await market_source.start(tickers)
    yield
    await market_source.stop()

app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(price_cache))
```

`price_cache` and `market_source` are **module-level singletons** imported directly by route
handlers — no dependency injection framework needed.

---

## Watchlist ↔ Market Source Coupling

The watchlist route handler owns keeping DB state and the live price set in sync:

```python
# POST /api/watchlist
db.add(WatchlistRow(ticker=ticker)); db.commit()
await market_source.add_ticker(ticker)

# DELETE /api/watchlist/{ticker}
if open_position_exists:
    raise HTTPException(400, "Cannot remove ticker with an open position")
db.delete(row); db.commit()
await market_source.remove_ticker(ticker)
```

**Trade auto-add:** the trade route handler auto-adds a ticker to the watchlist + market source
if it isn't already tracked, so a fill price always exists:

```python
if not watchlist_row_exists(ticker):
    db.add(WatchlistRow(ticker=ticker)); db.commit()
    await market_source.add_ticker(ticker)
fill_price = price_cache.get_price(ticker)  # guaranteed non-None after add
```

---

## Dependencies

```toml
# backend/pyproject.toml
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "numpy>=1.26",   # GBM Cholesky
    "massive",       # Polygon.io SDK; imported only inside MassiveDataSource
]
```

`massive` is always installed but only imported when `MASSIVE_API_KEY` is set, so the simulator
path and tests never make network calls.

---

## Component Summary Table

| Component | File | Role |
|-----------|------|------|
| `PriceUpdate` | `models.py` | Immutable data unit; SSE payload shape |
| `PriceCache` | `cache.py` | Thread-safe shared store; `version` for SSE change detection |
| `MarketDataSource` | `interface.py` | ABC; both implementations conform |
| Seed data | `seed_prices.py` | Authoritative start prices + GBM params (single source of truth) |
| `GBMSimulator` | `simulator.py` | Pure sync math: GBM + Cholesky correlations + event shocks |
| `SimulatorDataSource` | `simulator.py` | Async wrapper: 500 ms tick loop + cache writes |
| `MassiveDataSource` | `massive.py` | Async polling wrapper over sync SDK via `to_thread` |
| `create_market_data_source` | `factory.py` | Single env-var branch; returns unstarted source |
| SSE router | `stream.py` | `GET /api/stream/prices`; emit-on-change via version |
| Public API | `__init__.py` | `from app.market import ...` |
