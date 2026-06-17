# Market Interface — Unified Price API

The unified Python API that downstream code (SSE streaming, portfolio valuation, trade fills) uses
to read live prices, **without knowing or caring** whether the data comes from the
[Massive API](MASSIVE_API.md) or the [GBM simulator](MARKET_SIMULATOR.md).

## 1. Selection rule

```
MASSIVE_API_KEY set and non-empty  →  MassiveDataSource (real data)
otherwise                          →  SimulatorDataSource (GBM simulation)
```

Selection happens in one place — `create_market_data_source(cache)` — so the rest of the app never
branches on the data source.

## 2. Architecture

Both sources are **producers** that write into a shared **`PriceCache`**. Everything downstream is a
**consumer** that reads the cache. Sources never return prices directly to callers.

```
  ┌─────────────────────┐        writes        ┌──────────────┐      reads
  │ SimulatorDataSource  │ ───────────────────▶ │              │ ◀──────────── SSE /api/stream/prices
  │   OR                 │                      │  PriceCache  │ ◀──────────── trade fill (get_price)
  │ MassiveDataSource    │ ───────────────────▶ │  (in-memory) │ ◀──────────── portfolio valuation
  └─────────────────────┘   background task     └──────────────┘
            ▲                                          │ version++
            │ create_market_data_source(cache)         │
       MASSIVE_API_KEY?                          monotonic counter → SSE change detection
```

Why this shape:
- **One interface, two implementations** — swapping data sources is an env var, not a code change.
- **Cache decouples producer cadence from consumer cadence** — the simulator ticks every 500 ms and
  Massive polls every 2–15 s, but the SSE stream reads on its own ~500 ms schedule regardless.
- **Future multi-user ready** — consumers already go through a shared cache, not a per-request fetch.

## 3. The `MarketDataSource` interface

Abstract base class (`app/market/interface.py`). Both implementations conform; tests assert
conformance.

```python
class MarketDataSource(ABC):
    async def start(self, tickers: list[str]) -> None: ...   # begin background production
    async def stop(self) -> None: ...                        # cancel task, release resources
    async def add_ticker(self, ticker: str) -> None: ...     # track a new symbol
    async def remove_ticker(self, ticker: str) -> None: ...  # stop tracking + drop from cache
    def get_tickers(self) -> list[str]: ...                  # current active set
```

Lifecycle:

```python
source = create_market_data_source(cache)
await source.start(["AAPL", "GOOGL", "MSFT"])
# ... app runs ...
await source.add_ticker("TSLA")      # e.g. watchlist add / trade auto-add
await source.remove_ticker("GOOGL")  # watchlist remove
await source.stop()                  # app shutdown
```

Contract notes:
- `start()` is called **exactly once**; it kicks off one background task that writes to the cache.
- `stop()` is **idempotent** — safe to call multiple times.
- `add_ticker` / `remove_ticker` are **no-ops** if the ticker is already present / absent.
- `remove_ticker` also removes the ticker from the `PriceCache`, keeping live prices and tracked set
  in sync.

> **Watchlist coupling.** Per `PLAN.md`, the watchlist route handler owns the coupling: adding a
> watchlist row calls `source.add_ticker(...)`, removing one calls `source.remove_ticker(...)`. A
> trade auto-adds its ticker via the same path so a fill price always exists.

## 4. `PriceUpdate` — the data unit

Immutable dataclass (`app/market/models.py`). The single shape every consumer sees, identical
across both sources.

| Field / property | Meaning |
|------------------|---------|
| `ticker` | Symbol |
| `price` | Latest price (rounded to 2 dp on cache write) |
| `previous_price` | Price from the prior update (last tick, **not** day's close) |
| `timestamp` | Unix seconds |
| `change` | `price - previous_price` (4 dp) |
| `change_percent` | Percent change vs `previous_price` (4 dp) |
| `direction` | `"up"` / `"down"` / `"flat"` |
| `to_dict()` | JSON-serializable dict for SSE payloads |

> `previous_price` is the **last tick**, not a daily open/close. Per `PLAN.md` item 3, the frontend
> labels watchlist change as "since open/load" using the first price seen since page load — it does
> **not** derive a daily figure from `previous_price`.

## 5. `PriceCache` — shared store

Thread-safe in-memory cache (`app/market/cache.py`). One latest `PriceUpdate` per ticker.

```python
cache.update(ticker, price, timestamp=None) -> PriceUpdate  # writer; computes prev/change/direction
cache.get(ticker)        -> PriceUpdate | None
cache.get_price(ticker)  -> float | None                    # convenience for trade fills
cache.get_all()          -> dict[str, PriceUpdate]          # SSE snapshot
cache.remove(ticker)
cache.version            -> int   # monotonic; bumps on every update → SSE change detection
```

- **Thread-safe** via a `Lock` because the sync Massive client writes from a worker thread
  (`asyncio.to_thread`) while async consumers read.
- **`version`** lets the SSE endpoint push only when something actually changed (emit-on-change,
  polled at ~500 ms — `PLAN.md` item 2), rather than re-sending an unchanged snapshot.
- First update for a ticker sets `previous_price == price` → `direction == "flat"`.

## 6. The factory

```python
def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

Returns an **unstarted** source — the caller (app startup) owns `start(tickers)`.

## 7. SSE streaming consumer

`create_stream_router(price_cache)` mounts `GET /api/stream/prices` (`text/event-stream`). It:

1. Reads `price_cache.version` every ~500 ms.
2. On change, serializes `get_all()` to `{ticker: PriceUpdate.to_dict()}` and yields one
   `data: {...}` event.
3. Emits `retry: 1000` so the browser `EventSource` auto-reconnects.
4. Stops when `request.is_disconnected()`.

The stream is **source-agnostic** — it only knows the cache.

## 8. App wiring (startup / shutdown)

```python
cache = PriceCache()
source = create_market_data_source(cache)

@app.on_event("startup")
async def _startup():
    tickers = load_watchlist_tickers()   # from DB seed
    await source.start(tickers)

@app.on_event("shutdown")
async def _shutdown():
    await source.stop()

app.include_router(create_stream_router(cache))
```

## 9. Public imports

```python
from app.market import (
    PriceCache, PriceUpdate, MarketDataSource,
    create_market_data_source, create_stream_router,
)
```

## 10. Adding a future data source

Implement `MarketDataSource` (e.g. an Alpaca or IEX poller), have it write `PriceUpdate`s into the
cache, and add one branch to the factory. No consumer changes — SSE, valuation, and trade fills keep
working unchanged.

See [`MARKET_SIMULATOR.md`](MARKET_SIMULATOR.md) for the default (no-key) implementation and
[`MASSIVE_API.md`](MASSIVE_API.md) for the real-data implementation.
