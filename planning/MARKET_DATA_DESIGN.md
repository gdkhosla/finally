# Market Data — Implementation Design

This document is the implementation blueprint for all market data components:
`PriceCache`, `PriceUpdate`, `MarketDataSource` interface, `GBMSimulator`,
`SimulatorDataSource`, `MassiveDataSource`, the factory, and the SSE streaming
router. It contains working code ready to copy into `backend/app/market/`.

---

## File layout

```
backend/app/market/
├── __init__.py          # public re-exports
├── models.py            # PriceUpdate dataclass
├── cache.py             # PriceCache
├── interface.py         # MarketDataSource ABC
├── seed_prices.py       # GBM params + seed prices
├── simulator.py         # GBMSimulator + SimulatorDataSource
├── massive.py           # MassiveDataSource
├── factory.py           # create_market_data_source()
└── stream.py            # SSE router
```

---

## 1. `models.py` — PriceUpdate

```python
# backend/app/market/models.py
from dataclasses import dataclass, field
from time import time


@dataclass(frozen=True)
class PriceUpdate:
    ticker: str
    price: float
    previous_price: float
    timestamp: float  # Unix seconds

    @property
    def change(self) -> float:
        return round(self.price - self.previous_price, 4)

    @property
    def change_percent(self) -> float:
        if self.previous_price == 0:
            return 0.0
        return round((self.price - self.previous_price) / self.previous_price * 100, 4)

    @property
    def direction(self) -> str:
        if self.price > self.previous_price:
            return "up"
        if self.price < self.previous_price:
            return "down"
        return "flat"

    def to_dict(self) -> dict:
        return {
            "ticker": self.ticker,
            "price": self.price,
            "previous_price": self.previous_price,
            "timestamp": self.timestamp,
            "change": self.change,
            "change_percent": self.change_percent,
            "direction": self.direction,
        }
```

Key points:
- `frozen=True` — immutable; safe to hand off to multiple async consumers.
- `previous_price` is the **last tick**, not a daily close (per PLAN.md item 3).
- `change` / `change_percent` / `direction` are computed properties, not stored — no
  staleness risk.
- `to_dict()` is the SSE payload shape; downstream code must not hardcode field names.

---

## 2. `cache.py` — PriceCache

```python
# backend/app/market/cache.py
import threading
from time import time
from .models import PriceUpdate


class PriceCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prices: dict[str, PriceUpdate] = {}
        self._version: int = 0

    @property
    def version(self) -> int:
        return self._version

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        ts = timestamp if timestamp is not None else time()
        price = round(price, 2)
        with self._lock:
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price  # first update → flat
            update = PriceUpdate(
                ticker=ticker,
                price=price,
                previous_price=previous_price,
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
        return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)
            self._version += 1
```

Key points:
- `threading.Lock` (not `asyncio.Lock`) because `MassiveDataSource` calls `cache.update`
  from `asyncio.to_thread`, which runs on a worker thread. Async locks don't protect
  across thread boundaries.
- `version` is a plain `int` bumped on every write. The SSE loop compares snapshots of
  this integer — no polling of individual prices needed.
- First update for a ticker sets `previous_price = price` so `direction == "flat"`, which
  is correct: no prior data = no direction.
- `remove()` also bumps `version` so SSE can detect that a ticker disappeared.

---

## 3. `interface.py` — MarketDataSource ABC

```python
# backend/app/market/interface.py
from abc import ABC, abstractmethod


class MarketDataSource(ABC):

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin background production. Called exactly once at app startup."""

    @abstractmethod
    async def stop(self) -> None:
        """Cancel background task and release resources. Idempotent."""

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Start tracking a new symbol. No-op if already tracked."""

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Stop tracking a symbol and remove it from the cache. No-op if absent."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the currently tracked set."""
```

---

## 4. `seed_prices.py` — GBM parameters

```python
# backend/app/market/seed_prices.py

# Starting prices (authoritative; PLAN.md values are illustrative only)
SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  420.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  870.00,
    "META":  510.00,
    "JPM":   200.00,
    "V":     275.00,
    "NFLX":  625.00,
}

# Per-ticker GBM parameters: annualized drift (mu) and volatility (sigma)
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"mu": 0.05, "sigma": 0.22},
    "GOOGL": {"mu": 0.06, "sigma": 0.24},
    "MSFT":  {"mu": 0.07, "sigma": 0.20},
    "AMZN":  {"mu": 0.08, "sigma": 0.28},
    "TSLA":  {"mu": 0.03, "sigma": 0.50},  # high vol, low drift
    "NVDA":  {"mu": 0.10, "sigma": 0.40},  # high vol, high drift
    "META":  {"mu": 0.06, "sigma": 0.26},
    "JPM":   {"mu": 0.05, "sigma": 0.17},
    "V":     {"mu": 0.06, "sigma": 0.18},
    "NFLX":  {"mu": 0.04, "sigma": 0.30},
}

# Params for unknown tickers added dynamically via watchlist / trade auto-add
DEFAULT_PARAMS: dict[str, float] = {"mu": 0.05, "sigma": 0.25}

# Sector membership for correlation matrix
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
    # TSLA is intentionally absent — treated as its own uncorrelated name
}

# Pairwise correlation coefficients
INTRA_TECH_CORR: float    = 0.6
INTRA_FINANCE_CORR: float = 0.5
CROSS_GROUP_CORR: float   = 0.3
TSLA_CORR: float          = 0.3  # TSLA vs everything
```

> The seed prices here are the **single source of truth**. Numeric values in other docs
> (PLAN.md, comments) are illustrative only.

---

## 5. `simulator.py` — GBMSimulator + SimulatorDataSource

### 5a. GBMSimulator (pure math, no async)

```python
# backend/app/market/simulator.py
import math
import random
import numpy as np
from .seed_prices import (
    SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
    CORRELATION_GROUPS, INTRA_TECH_CORR, INTRA_FINANCE_CORR,
    CROSS_GROUP_CORR, TSLA_CORR,
)

# 252 trading days × 6.5 hours × 3600 seconds = one trading year in seconds
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # 500 ms as a year-fraction
DEFAULT_EVENT_PROBABILITY = 0.001             # 0.1% per tick per ticker


class GBMSimulator:
    """
    Pure price engine. Synchronous and stateless w.r.t. asyncio.
    Unit-testable without any async machinery.
    """

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = DEFAULT_EVENT_PROBABILITY,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._tickers: list[str] = []
        self._chol: np.ndarray | None = None  # Cholesky factor, rebuilt on membership change

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    # ── public interface ──────────────────────────────────────────────────────

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: new_price}."""
        n = len(self._tickers)
        if n == 0:
            return {}

        # Draw correlated normals via Cholesky decomposition
        z = np.random.standard_normal(n)
        z_corr = self._chol @ z  # shape (n,)

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            p = self._prices[ticker]
            mu = self._params[ticker]["mu"]
            sigma = self._params[ticker]["sigma"]
            dt = self._dt

            # GBM discrete step: S(t+dt) = S(t) * exp((mu - σ²/2)*dt + σ*√dt*Z)
            drift = (mu - 0.5 * sigma ** 2) * dt
            diffusion = sigma * math.sqrt(dt) * z_corr[i]
            new_price = p * math.exp(drift + diffusion)

            # Random event shock: ±2–5% spike, 0.1% probability
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                new_price *= (1 + shock)

            new_price = max(round(new_price, 2), 0.01)  # floor at 1 cent
            self._prices[ticker] = new_price
            result[ticker] = new_price

        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # ── internals ─────────────────────────────────────────────────────────────

    def _add_ticker_internal(self, ticker: str) -> None:
        params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
        seed = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._tickers.append(ticker)
        self._prices[ticker] = round(seed, 2)
        self._params[ticker] = params

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n == 0:
            self._chol = np.zeros((0, 0))
            return

        # Build correlation matrix
        C = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._correlation(self._tickers[i], self._tickers[j])
                C[i, j] = rho
                C[j, i] = rho

        # Cholesky decomposition; add small jitter if not positive-definite
        try:
            L = np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            C += np.eye(n) * 1e-6
            L = np.linalg.cholesky(C)
        self._chol = L

    def _correlation(self, a: str, b: str) -> float:
        if a == "TSLA" or b == "TSLA":
            return TSLA_CORR
        for group, members in CORRELATION_GROUPS.items():
            if a in members and b in members:
                if group == "tech":
                    return INTRA_TECH_CORR
                if group == "finance":
                    return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

### 5b. SimulatorDataSource (async lifecycle)

```python
import asyncio
import logging
from time import time
from .interface import MarketDataSource
from .cache import PriceCache

logger = logging.getLogger(__name__)


class SimulatorDataSource(MarketDataSource):
    """Wraps GBMSimulator, drives the background tick loop, writes to PriceCache."""

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        dt: float = DEFAULT_DT,
        event_probability: float = DEFAULT_EVENT_PROBABILITY,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._dt = dt
        self._event_prob = event_probability
        self._engine: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._engine = GBMSimulator(tickers, dt=self._dt, event_probability=self._event_prob)
        # Seed the cache immediately so the first SSE connection has data
        for ticker, price in self._engine._prices.items():
            self._cache.update(ticker, price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def add_ticker(self, ticker: str) -> None:
        if self._engine is None:
            return
        self._engine.add_ticker(ticker)
        price = self._engine.get_price(ticker)
        if price is not None:
            self._cache.update(ticker, price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._engine is None:
            return
        self._engine.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._engine.get_tickers() if self._engine else []

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                if self._engine is None:
                    continue
                prices = self._engine.step()
                ts = time()
                for ticker, price in prices.items():
                    self._cache.update(ticker, price, timestamp=ts)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Simulator tick error — continuing")
```

---

## 6. `massive.py` — MassiveDataSource

```python
# backend/app/market/massive.py
import asyncio
import logging
import os
from time import time
from .interface import MarketDataSource
from .cache import PriceCache

logger = logging.getLogger(__name__)

# Poll every 15 s on free tier (5 req/min). Paid tiers can reduce to 2-5 s.
DEFAULT_POLL_INTERVAL = 15.0


class MassiveDataSource(MarketDataSource):
    """
    Polls the Massive (Polygon.io) REST API for live prices.
    The SDK is synchronous; all blocking calls run in asyncio.to_thread().
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None
        self._client = None  # created lazily in start()

    async def start(self, tickers: list[str]) -> None:
        # Import here so tests without the massive package don't fail at import time
        from massive import RESTClient
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = set(tickers)
        # Fetch once immediately so the cache is populated before returning
        await self._poll_once()
        self._task = asyncio.create_task(self._run_loop(), name="massive-poll-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Massive poll error — will retry next cycle")

    async def _poll_once(self) -> None:
        if not self._tickers:
            return
        tickers_list = list(self._tickers)
        snapshots = await asyncio.to_thread(self._fetch_snapshots, tickers_list)
        ts = time()
        for snap in snapshots:
            try:
                price = snap.last_trade.price
                # SDK normalizes timestamp to milliseconds; convert to seconds
                ts_snap = snap.last_trade.timestamp / 1000.0
            except (AttributeError, TypeError):
                logger.debug("Skipping %s — missing last_trade data", getattr(snap, "ticker", "?"))
                continue
            self._cache.update(ticker=snap.ticker, price=price, timestamp=ts_snap)

    def _fetch_snapshots(self, tickers: list[str]):
        """Synchronous — runs in a worker thread via asyncio.to_thread."""
        from massive.rest.models import SnapshotMarketType
        try:
            return list(
                self._client.get_snapshot_all(
                    market_type=SnapshotMarketType.STOCKS,
                    tickers=tickers,
                )
            )
        except Exception:
            logger.exception("Massive get_snapshot_all failed")
            return []
```

Error handling philosophy:
- `_fetch_snapshots` catches all SDK exceptions and returns `[]`. The caller logs and skips.
- Per-ticker `AttributeError`/`TypeError` is handled individually — one bad ticker never
  poisons the batch.
- The poll loop catches all non-`CancelledError` exceptions so a transient 429/401 never
  kills the background task.

---

## 7. `factory.py` — create_market_data_source

```python
# backend/app/market/factory.py
import os
from .cache import PriceCache
from .interface import MarketDataSource
from .simulator import SimulatorDataSource
from .massive import MassiveDataSource


def create_market_data_source(price_cache: PriceCache) -> MarketDataSource:
    """
    Returns an unstarted MarketDataSource. Selection rule:
      MASSIVE_API_KEY set and non-empty  →  MassiveDataSource
      otherwise                          →  SimulatorDataSource
    """
    api_key = os.environ.get("MASSIVE_API_KEY", "").strip()
    if api_key:
        return MassiveDataSource(api_key=api_key, price_cache=price_cache)
    return SimulatorDataSource(price_cache=price_cache)
```

The factory is the **only** place the env var is inspected. All other code receives a
`MarketDataSource` and is completely agnostic to which implementation it holds.

---

## 8. `stream.py` — SSE router

```python
# backend/app/market/stream.py
import asyncio
import json
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from .cache import PriceCache

SSE_POLL_INTERVAL = 0.5   # seconds between cache version checks
SSE_RETRY_MS      = 1000  # tells EventSource to wait 1 s before reconnecting


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter()

    @router.get("/api/stream/prices")
    async def stream_prices(request: Request):
        return StreamingResponse(
            _price_generator(request, price_cache),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable nginx buffering if behind proxy
            },
        )

    return router


async def _price_generator(request: Request, cache: PriceCache):
    # Emit retry directive once so browser EventSource reconnects quickly
    yield f"retry: {SSE_RETRY_MS}\n\n"

    last_version = -1

    while True:
        # Check for client disconnect
        if await request.is_disconnected():
            break

        current_version = cache.version
        if current_version != last_version:
            last_version = current_version
            all_prices = cache.get_all()
            payload = {ticker: update.to_dict() for ticker, update in all_prices.items()}
            yield f"data: {json.dumps(payload)}\n\n"

        await asyncio.sleep(SSE_POLL_INTERVAL)
```

SSE event format (browser-compatible):
```
retry: 1000

data: {"AAPL": {"ticker": "AAPL", "price": 191.42, "previous_price": 191.38, ...}, ...}

data: {"AAPL": {...}, "MSFT": {...}}
```

- **Emit-on-change** via `version` comparison — no noise if nothing moved.
- **Full snapshot per event** — client replaces its price map entirely rather than
  applying diffs. Simpler and safe for reconnection: one event makes the client current.
- `X-Accel-Buffering: no` prevents nginx from batching SSE frames when deployed behind
  a reverse proxy.
- `is_disconnected()` is awaited inside the sleep gap; if FastAPI's implementation raises
  on a closed connection, the generator exits cleanly.

### Frontend EventSource usage (reference for frontend engineer)

```typescript
const es = new EventSource("/api/stream/prices");

es.onmessage = (event) => {
  const prices: Record<string, PriceUpdate> = JSON.parse(event.data);
  // prices["AAPL"].price, prices["AAPL"].direction, etc.
  dispatch(setPrices(prices));
};

es.onerror = () => {
  // EventSource reconnects automatically; onerror fires on each retry
  setConnectionStatus("reconnecting");
};
```

---

## 9. `__init__.py` — public re-exports

```python
# backend/app/market/__init__.py
from .cache import PriceCache
from .models import PriceUpdate
from .interface import MarketDataSource
from .factory import create_market_data_source
from .stream import create_stream_router

__all__ = [
    "PriceCache",
    "PriceUpdate",
    "MarketDataSource",
    "create_market_data_source",
    "create_stream_router",
]
```

Downstream imports use only this surface:

```python
from app.market import PriceCache, create_market_data_source, create_stream_router
```

---

## 10. App wiring (FastAPI lifespan)

```python
# backend/app/main.py (relevant excerpt)
from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.market import PriceCache, create_market_data_source, create_stream_router
from app.db import load_watchlist_tickers  # returns list[str] from DB

price_cache = PriceCache()
market_source = create_market_data_source(price_cache)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tickers = await load_watchlist_tickers()   # seeded default 10 tickers
    await market_source.start(tickers)
    yield
    await market_source.stop()


app = FastAPI(lifespan=lifespan)
app.include_router(create_stream_router(price_cache))
```

`market_source` and `price_cache` are module-level singletons. Route handlers (watchlist,
trade) import them directly — no dependency injection framework needed at this scale.

---

## 11. Watchlist route handler coupling

Per PLAN.md, the watchlist handler owns the coupling between DB state and the live
price set. Example:

```python
# backend/app/routes/watchlist.py (excerpt)
from app.market import market_source  # the module-level singleton

@router.post("/api/watchlist")
async def add_ticker(body: AddTickerRequest, db: Session = Depends(get_db)):
    db.add(WatchlistRow(ticker=body.ticker))
    db.commit()
    await market_source.add_ticker(body.ticker)   # sync DB + price cache
    return {"ticker": body.ticker}

@router.delete("/api/watchlist/{ticker}")
async def remove_ticker(ticker: str, db: Session = Depends(get_db)):
    if db.query(Position).filter_by(ticker=ticker, quantity>0).first():
        raise HTTPException(400, "Cannot remove ticker with an open position")
    db.delete(db.query(WatchlistRow).filter_by(ticker=ticker).one())
    db.commit()
    await market_source.remove_ticker(ticker)     # sync DB + price cache
    return {"ticker": ticker}
```

Trade auto-add (in the trade route handler):
```python
# backend/app/routes/portfolio.py (excerpt)
async def execute_trade(body: TradeRequest, db: Session = Depends(get_db)):
    # Auto-add to watchlist + market source if not already tracked
    if not db.query(WatchlistRow).filter_by(ticker=body.ticker).first():
        db.add(WatchlistRow(ticker=body.ticker))
        db.commit()
        await market_source.add_ticker(body.ticker)

    fill_price = price_cache.get_price(body.ticker)
    if fill_price is None:
        raise HTTPException(503, "No price available for ticker")
    # ... rest of trade logic ...
```

---

## 12. Unit test sketch

```python
# backend/tests/market/test_simulator.py
import pytest
from app.market.simulator import GBMSimulator
from app.market.cache import PriceCache
from app.market.models import PriceUpdate

def test_gbm_prices_positive():
    sim = GBMSimulator(["AAPL", "MSFT"])
    for _ in range(100):
        prices = sim.step()
    assert all(p > 0 for p in prices.values())

def test_correlated_tickers_covariance():
    """AAPL and MSFT (both tech) should show positive correlation over many steps."""
    sim = GBMSimulator(["AAPL", "MSFT"], event_probability=0)
    aapl_returns, msft_returns = [], []
    prev = {"AAPL": sim.get_price("AAPL"), "MSFT": sim.get_price("MSFT")}
    for _ in range(1000):
        prices = sim.step()
        aapl_returns.append((prices["AAPL"] - prev["AAPL"]) / prev["AAPL"])
        msft_returns.append((prices["MSFT"] - prev["MSFT"]) / prev["MSFT"])
        prev = dict(prices)
    cov = sum(a * b for a, b in zip(aapl_returns, msft_returns)) / len(aapl_returns)
    assert cov > 0, "Expect positive covariance for correlated sector tickers"

def test_add_remove_ticker_rebuilds_cholesky():
    sim = GBMSimulator(["AAPL"])
    sim.add_ticker("TSLA")
    assert "TSLA" in sim.get_tickers()
    prices = sim.step()  # should not raise
    assert "TSLA" in prices
    sim.remove_ticker("TSLA")
    prices = sim.step()
    assert "TSLA" not in prices

def test_price_cache_version_bumps():
    cache = PriceCache()
    v0 = cache.version
    cache.update("AAPL", 190.0)
    assert cache.version == v0 + 1

def test_price_cache_first_update_flat():
    cache = PriceCache()
    u = cache.update("AAPL", 190.0)
    assert u.direction == "flat"
    assert u.change == 0.0

def test_price_cache_direction():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    u = cache.update("AAPL", 191.0)
    assert u.direction == "up"
    u2 = cache.update("AAPL", 189.0)
    assert u2.direction == "down"

@pytest.mark.asyncio
async def test_simulator_data_source_seeds_cache():
    from app.market.simulator import SimulatorDataSource
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=0.1)
    await src.start(["AAPL", "GOOGL"])
    # Cache should be seeded immediately after start()
    assert cache.get_price("AAPL") is not None
    assert cache.get_price("GOOGL") is not None
    await src.stop()
```

---

## 13. Dependencies

Add to `backend/pyproject.toml`:

```toml
[project]
dependencies = [
    "fastapi>=0.111",
    "uvicorn[standard]>=0.29",
    "numpy>=1.26",        # GBM Cholesky
    "massive",            # Polygon.io SDK (only used when MASSIVE_API_KEY is set)
    # ... other backend deps ...
]
```

`massive` is always installed (it's a small SDK). It is only *imported* inside
`MassiveDataSource`, so tests without a key don't make any network calls.

---

## Summary

| Component | File | Role |
|-----------|------|------|
| `PriceUpdate` | `models.py` | Immutable data unit; SSE payload shape |
| `PriceCache` | `cache.py` | Thread-safe shared store; `version` for SSE change detection |
| `MarketDataSource` | `interface.py` | ABC; both implementations conform |
| Seed data | `seed_prices.py` | Authoritative start prices + GBM params |
| `GBMSimulator` | `simulator.py` | Pure sync math: GBM + Cholesky correlations + events |
| `SimulatorDataSource` | `simulator.py` | Async wrapper: tick loop + cache writes |
| `MassiveDataSource` | `massive.py` | Async polling wrapper over sync SDK via `to_thread` |
| `create_market_data_source` | `factory.py` | Single env-var branch; returns unstarted source |
| SSE router | `stream.py` | `GET /api/stream/prices`; emit-on-change via version |
| Public API | `__init__.py` | `from app.market import ...` |
