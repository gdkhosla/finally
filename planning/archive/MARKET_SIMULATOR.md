# Market Simulator — Approach & Code Structure

The default market data source when `MASSIVE_API_KEY` is **not** set. It generates realistic,
continuously-moving stock prices entirely in-process — no network, no API key, deterministic shape.
It implements the same [`MarketDataSource`](MARKET_INTERFACE.md) interface as the real Massive
client, so nothing downstream knows the difference.

## 1. Goals

- **Realistic motion** — prices wander like real stocks: small random ticks that accumulate into
  trends, not white noise around a fixed point.
- **Correlated sectors** — tech names move together, financials move together, TSLA does its own
  thing. The watchlist feels like a real market on a given day.
- **Occasional drama** — rare sudden 2–5% jumps to make the demo visually interesting.
- **Cheap** — runs as one async background task ticking every 500 ms; fast enough for dozens of
  tickers.

## 2. The model: Geometric Brownian Motion (GBM)

GBM is the standard model for stock-price simulation. Prices stay positive and move
multiplicatively (percentage moves), matching how equities behave.

Discrete step:

```
S(t+dt) = S(t) * exp( (mu - sigma^2 / 2) * dt  +  sigma * sqrt(dt) * Z )
```

| Symbol | Meaning |
|--------|---------|
| `S(t)` | current price |
| `mu` | annualized drift (expected return) |
| `sigma` | annualized volatility |
| `dt` | time step as a fraction of a trading year |
| `Z` | a (correlated) standard-normal random draw |

### Time scaling

`dt` is tiny so each 500 ms tick produces sub-cent moves that accumulate naturally:

```
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  = 5,896,800   # 252 days * 6.5h * 3600s
DEFAULT_DT               = 0.5 / 5,896,800    ≈ 8.48e-8     # 500 ms as a year-fraction
```

This is what keeps a $190 stock drifting by pennies per tick rather than dollars.

## 3. Correlation via Cholesky decomposition

Independent random draws would make every ticker wiggle on its own — unrealistic. Instead the
simulator draws **correlated** normals:

1. Build an `n × n` correlation matrix `C` from sector membership.
2. Compute its Cholesky factor `L` (so `L Lᵀ = C`).
3. Each tick: draw independent normals `z`, then `z_correlated = L @ z`. Component `i` feeds ticker
   `i`'s diffusion term.

Pairwise correlation rules (`seed_prices.py`):

| Pair | ρ |
|------|---|
| Same tech sector | 0.6 |
| Same finance sector | 0.5 |
| Cross-sector / unknown | 0.3 |
| Anything with TSLA | 0.3 (independent) |

The Cholesky factor is rebuilt whenever a ticker is added or removed (`O(n²)`, trivial for n < 50).

## 4. Random events

Each tick, each ticker has `event_probability` (~0.1%) of a shock:

```python
if random.random() < event_prob:
    shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])  # ±2–5%
    price *= (1 + shock)
```

With 10 tickers at 2 ticks/sec, expect a shock roughly every ~50 seconds — enough for visual
interest without chaos.

## 5. Seed data (`seed_prices.py`)

Single source of truth for starting prices and per-ticker GBM params.

```python
SEED_PRICES   = {"AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, ...}   # realistic starts
TICKER_PARAMS = {"AAPL": {"sigma": 0.22, "mu": 0.05}, "TSLA": {"sigma": 0.50, "mu": 0.03}, ...}
DEFAULT_PARAMS = {"sigma": 0.25, "mu": 0.05}   # for dynamically added unknown tickers

CORRELATION_GROUPS = {"tech": {AAPL, GOOGL, MSFT, AMZN, META, NVDA, NFLX}, "finance": {JPM, V}}
INTRA_TECH_CORR, INTRA_FINANCE_CORR, CROSS_GROUP_CORR, TSLA_CORR = 0.6, 0.5, 0.3, 0.3
```

- Volatility tuned per name: TSLA `0.50` (wild), NVDA `0.40` (high), JPM/V `0.17–0.18` (calm).
- Unknown tickers (added via watchlist/trade) get a random seed price in `[50, 300]` and
  `DEFAULT_PARAMS`.

## 6. Code structure

Two classes in `app/market/simulator.py`, separating **math** from **lifecycle**.

### `GBMSimulator` — pure price engine (no async, no cache)

| Method | Role |
|--------|------|
| `__init__(tickers, dt, event_probability)` | seed prices/params, build Cholesky |
| `step() -> dict[str, float]` | advance all tickers one tick; the hot path |
| `add_ticker(ticker)` / `remove_ticker(ticker)` | mutate set, rebuild Cholesky |
| `get_price(ticker)` / `get_tickers()` | inspect current state |

`step()` is the core loop: draw `n` normals, apply Cholesky, then per ticker compute
`drift + diffusion`, multiply into the price, maybe apply an event, round to 2 dp.

### `SimulatorDataSource(MarketDataSource)` — async lifecycle + cache wiring

Wraps `GBMSimulator` and fulfills the interface:

| Method | Behavior |
|--------|----------|
| `start(tickers)` | build the engine, seed the cache immediately, launch `_run_loop()` |
| `_run_loop()` | every `update_interval` (0.5 s): `step()` → `cache.update(...)` per ticker |
| `add_ticker` / `remove_ticker` | delegate to engine; seed/clear the ticker in the cache |
| `stop()` | cancel the background task (idempotent) |
| `get_tickers()` | proxy to the engine |

The loop catches and logs exceptions so one bad tick never kills the task. Initial prices are
written to the cache in `start()` so SSE has data on the very first connection.

## 7. Why this design

- **Math/lifecycle split** — `GBMSimulator` is synchronous and unit-testable in isolation (verify
  GBM formula, correlation, events); `SimulatorDataSource` handles asyncio and cache I/O.
- **Identical contract to Massive** — same `start/stop/add/remove`, same `PriceUpdate`s in the cache,
  so the factory swap is invisible downstream.
- **Self-contained** — depends only on `numpy` + stdlib `random`/`math`; no external services, ideal
  for tests, CI, and offline demos.

## 8. Testing notes

- `GBMSimulator.step()` returns positive prices; over many steps the mean log-return tracks `mu`.
- Correlated tickers (e.g. AAPL/MSFT) show positive co-movement over a long run.
- Adding/removing tickers keeps the correlation matrix valid (Cholesky succeeds → matrix stays
  positive-definite).
- `SimulatorDataSource` writes to the cache within one interval of `start()` and stops cleanly.

See [`MARKET_INTERFACE.md`](MARKET_INTERFACE.md) for how this source plugs into the cache and SSE,
and [`MASSIVE_API.md`](MASSIVE_API.md) for the real-data alternative.
