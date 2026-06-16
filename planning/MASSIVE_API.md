# Massive API — Stock Prices (Research & Reference)

Massive (formerly **Polygon.io**) provides REST APIs for US equities: real-time / delayed
snapshots, previous-close, and historical aggregate bars. The Python SDK is a drop-in rebrand
of `polygon-api-client`, so the endpoints and response models below mirror Polygon's `/v1`–`/v3`
paths.

This document covers only what FinAlly needs: **latest prices for many tickers at once**
(real-time) and **end-of-day prices** (EOD). It is the source material for
[`MARKET_INTERFACE.md`](MARKET_INTERFACE.md).

---

## 1. Setup

```bash
uv add massive
```

```python
from massive import RESTClient

client = RESTClient(api_key="YOUR_MASSIVE_API_KEY")
```

- The key comes from the `MASSIVE_API_KEY` environment variable (see `.env`).
- The `RESTClient` is **synchronous**. In an async app (FastAPI), wrap calls in
  `asyncio.to_thread(...)` so they don't block the event loop.
- Auth is sent automatically by the SDK. Raw HTTP callers pass `?apiKey=` or
  `Authorization: Bearer <key>`.

### Tiers & rate limits

| Tier | Data | Rate limit | Suggested poll interval |
|------|------|-----------|-------------------------|
| Free | 15-min delayed | 5 requests/min | 15 s |
| Starter / paid | real-time | higher / unlimited | 2–5 s |

FinAlly polls the **snapshot-all** endpoint once per interval for the *union of all watched
tickers* — one request covers every ticker, so the rate limit applies per poll cycle, not per
ticker.

---

## 2. Real-time prices for many tickers — Snapshot All

The primary endpoint for FinAlly. One call returns the latest snapshot for every requested
ticker.

**REST:** `GET /v2/snapshot/locale/us/markets/stocks/tickers?tickers=AAPL,MSFT,GOOGL`

**SDK:**

```python
from massive import RESTClient
from massive.rest.models import SnapshotMarketType

client = RESTClient(api_key=API_KEY)

snapshots = client.get_snapshot_all(
    market_type=SnapshotMarketType.STOCKS,
    tickers=["AAPL", "MSFT", "GOOGL"],   # omit to fetch the entire market
)

for snap in snapshots:
    print(snap.ticker, snap.last_trade.price, snap.last_trade.timestamp)
```

### TickerSnapshot response model

| Field | Type | Meaning |
|-------|------|---------|
| `ticker` | str | Symbol, e.g. `"AAPL"` |
| `last_trade.price` | float | **Latest trade price** (what FinAlly uses for the fill/cache) |
| `last_trade.size` | int | Trade size |
| `last_trade.timestamp` | int | Trade time. **Units vary** — see note below |
| `last_quote.bid_price` / `ask_price` | float | NBBO bid/ask |
| `day.open / high / low / close / volume / vwap` | float | Current session aggregate |
| `prev_day.open / high / low / close / volume / vwap` | float | Previous session aggregate |
| `min.open / high / low / close / volume` | float | Current-minute bar |
| `todays_change` | float | Absolute change vs previous close |
| `todays_change_percent` | float | Percent change vs previous close |
| `updated` | int | Last-updated timestamp (nanoseconds in raw API) |

> **Timestamp units.** The raw Polygon/Massive API reports trade timestamps in **nanoseconds**;
> the Python SDK normalizes `last_trade.timestamp` to **milliseconds**. FinAlly converts to Unix
> seconds with `timestamp / 1000.0`. Always confirm units against the SDK version in
> `uv.lock` before relying on them.

### Robust extraction

Snapshots can have missing/null fields (illiquid ticker, pre-market, bad symbol). Read defensively
and skip what you can't parse rather than failing the whole poll:

```python
for snap in snapshots:
    try:
        price = snap.last_trade.price
        ts_seconds = snap.last_trade.timestamp / 1000.0
    except (AttributeError, TypeError):
        continue  # skip this ticker this cycle
    cache.update(ticker=snap.ticker, price=price, timestamp=ts_seconds)
```

### Single-ticker snapshot

`GET /v2/snapshot/locale/us/markets/stocks/tickers/{ticker}` →
`client.get_snapshot_ticker(market_type=SnapshotMarketType.STOCKS, ticker="AAPL")`.
FinAlly doesn't need this — the multi-ticker call is strictly more efficient.

---

## 3. End-of-day prices

### 3a. Previous close (single ticker)

**REST:** `GET /v2/aggs/ticker/{ticker}/prev`

```python
agg = client.get_previous_close_agg(ticker="AAPL")
# agg[0].close, agg[0].open, agg[0].high, agg[0].low, agg[0].volume, agg[0].vwap, agg[0].timestamp
```

### 3b. Daily open/close for a date

**REST:** `GET /v1/open-close/{ticker}/{date}` (date = `YYYY-MM-DD`)

```python
oc = client.get_daily_open_close_agg(ticker="AAPL", date="2026-06-15")
# oc.open, oc.high, oc.low, oc.close, oc.volume, oc.after_hours, oc.pre_market
```

### 3c. Aggregate bars / history (single ticker, date range)

**REST:** `GET /v2/aggs/ticker/{ticker}/range/{multiplier}/{timespan}/{from}/{to}`

```python
# Daily bars for AAPL over a range. list_aggs paginates automatically.
bars = []
for a in client.list_aggs(
    ticker="AAPL", multiplier=1, timespan="day",
    from_="2026-01-01", to="2026-06-15", limit=50000,
):
    bars.append(a)
# each: a.open, a.high, a.low, a.close, a.volume, a.vwap, a.timestamp (ms)
```

`timespan` ∈ `minute | hour | day | week | month | quarter | year`.

### 3d. Grouped daily — every ticker's EOD for one date (one call)

The EOD analogue of snapshot-all: a single request returns the daily bar for the whole US market.

**REST:** `GET /v2/aggs/grouped/locale/us/market/stocks/{date}`

```python
results = client.get_grouped_daily_aggs(date="2026-06-15")
for bar in results:
    print(bar.ticker, bar.close, bar.volume)
```

Use this if FinAlly ever needs to seed/backfill closing prices for many tickers cheaply.

---

## 4. Endpoint summary

| Need | REST path | SDK method |
|------|-----------|-----------|
| Realtime, many tickers | `/v2/snapshot/locale/us/markets/stocks/tickers` | `get_snapshot_all` |
| Realtime, one ticker | `/v2/snapshot/.../tickers/{ticker}` | `get_snapshot_ticker` |
| Previous close | `/v2/aggs/ticker/{ticker}/prev` | `get_previous_close_agg` |
| Daily open/close | `/v1/open-close/{ticker}/{date}` | `get_daily_open_close_agg` |
| History bars | `/v2/aggs/ticker/{t}/range/{m}/{ts}/{from}/{to}` | `get_aggs` / `list_aggs` |
| All-market EOD | `/v2/aggs/grouped/locale/us/market/stocks/{date}` | `get_grouped_daily_aggs` |

---

## 5. Error handling & operational notes

- **401** — missing/invalid key. Surface clearly at startup; the factory only selects Massive when
  `MASSIVE_API_KEY` is non-empty.
- **429** — rate limit. On the free tier keep the poll interval ≥ 15 s. The poller should swallow
  errors and retry next cycle rather than crash the loop.
- **Empty / partial results** — markets closed, pre-market, or unknown symbol. Skip per-ticker,
  don't fail the batch.
- **Delayed data** — free tier is 15-min delayed; acceptable for a simulated trading demo.
- **Blocking I/O** — the SDK is sync; always call it via `asyncio.to_thread` in the async backend.
- **Poll, don't stream** — FinAlly uses REST polling (works on all tiers), not the WebSocket feed.

This realtime + EOD surface is exactly what the unified market interface wraps; see
[`MARKET_INTERFACE.md`](MARKET_INTERFACE.md).
