# Market Data Backend — Code Review

**Reviewer:** Code review pass (automated)
**Date:** 2026-06-16
**Scope:** `backend/app/market/` implementation + `backend/tests/market/` test suite
**Reference docs:** `PLAN.md`, `MARKET_DATA_DESIGN.md`, `MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, `MASSIVE_API.md`

---

## Executive Summary

The market data subsystem is **well-built and ready to integrate** with the rest of
the platform. The production code faithfully implements the design documents — the
interface, cache, GBM simulator, Massive poller, factory, and SSE router all match
`MARKET_DATA_DESIGN.md` essentially line-for-line.

- **Test results:** 91 passed, 0 failed (all green after fixes below).
- **Spec compliance:** High. All PLAN.md decisions (items 2, 3, 4, 5) are respected.
- **Architecture:** Clean producer/cache/consumer split; source-agnostic downstream.
- **Recommendation:** Approved to build on.

### Resolution status (all issues below addressed)

| # | Issue | Status |
|---|-------|--------|
| 1 | `test_tsla_correlation_is_independent` asserted raw covariance | ✅ Fixed — now compares Pearson correlation coefficient (normalized), stable 5/5 |
| 2 | `SimulatorDataSource.start()` read engine private `_prices` | ✅ Fixed — added `GBMSimulator.get_all_prices()`, used in `start()` |
| 3 | Unknown tickers shared the `DEFAULT_PARAMS` dict object | ✅ Fixed — store a copy via `dict(...)` |
| 4 | Unused `from time import time` in `models.py` | ✅ Fixed — removed |
| 5 | No committed lockfile | ✅ Fixed — `uv.lock` committed |
| — | Missing hatch build target broke `uv run` | ✅ Fixed — added `[tool.hatch.build.targets.wheel] packages = ["app"]` |
| 6 | `cache.version` read without lock | Accepted as-is (atomic int read under CPython) |
| 7 | `_run_loop` dead `_engine is None` guard | Accepted as-is (harmless defensiveness) |

---

## Test Results

Run via an ephemeral environment (`uv run --no-project --with pytest --with
pytest-asyncio --with numpy --with fastapi --with httpx python -m pytest -v`),
because no `uv.lock` / virtualenv is checked in.

```
91 tests collected
90 passed, 1 failed in 2.21s

FAILED tests/market/test_simulator.py::test_tsla_correlation_is_independent
  assert cov_tech > cov_tsla
  assert 2.229043664875175e-09 > 2.681883043349895e-09
```

The failure reproduces **5/5 times** — it is deterministic, not flaky.

Per-file breakdown (all passing except the one noted):
- `test_cache.py` — PriceCache semantics, versioning, thread fields
- `test_factory.py` — env-var selection (empty / whitespace / set), unstarted source
- `test_interface.py` — ABC conformance for both sources
- `test_massive.py` — poll loop, ms→s conversion, defensive skip, idempotent stop
- `test_models.py` — PriceUpdate properties, frozen immutability, to_dict shape
- `test_simulator.py` — GBM positivity, add/remove + Cholesky rebuild, correlation
- `test_stream.py` — SSE retry directive, emit-on-change, disconnect handling

### Environment note (Issue #5)
There is no committed lockfile (`uv.lock`) and `pytest` is not available in the
base interpreter. The suite only runs after pulling test deps. A `uv.lock`
should be committed so tests are reproducible in CI and the Docker build.

---

## Spec Compliance

| Spec requirement (source) | Status | Notes |
|---|---|---|
| Two implementations, one `MarketDataSource` interface (INTERFACE §3) | ✅ Met | Both subclass the ABC; `test_interface.py` asserts conformance |
| Factory selects on `MASSIVE_API_KEY`, only place env is read (PLAN §5, INTERFACE §6) | ✅ Met | `factory.py`; `.strip()` handles whitespace-only keys |
| Shared in-memory `PriceCache`, latest+prev+timestamp (PLAN §6) | ✅ Met | `cache.py` stores one `PriceUpdate` per ticker |
| Thread-safe cache (sync Massive writes from worker thread) (DESIGN §2) | ✅ Met | `threading.Lock`; correct choice over `asyncio.Lock` |
| Version-based change detection for SSE (PLAN item 2) | ✅ Met | `version` int bumped on every write/remove |
| SSE emits on change, polled ~500ms (PLAN item 2) | ✅ Met | `stream.py` compares `cache.version` every 0.5s |
| `previous_price` = last tick, not daily close (PLAN item 3) | ✅ Met | Documented; frontend owns "since open/load" baseline |
| GBM with per-ticker drift/vol (PLAN §6, SIMULATOR §2) | ✅ Met | `simulator.py` discrete GBM step |
| Correlated moves via Cholesky (SIMULATOR §3) | ✅ Met | Rebuilt on membership change; jitter fallback if not PD |
| Occasional 2–5% event shocks (PLAN §6, SIMULATOR §4) | ✅ Met | 0.1%/tick, ±2–5% |
| Seed prices authoritative in `seed_prices.py` (PLAN item 14) | ✅ Met | Matches DESIGN values exactly |
| Unknown tickers get default params + random seed (SIMULATOR §5) | ✅ Met | `DEFAULT_PARAMS`, seed in [50,300] |
| `add_ticker`/`remove_ticker`; remove drops from cache (INTERFACE §3) | ✅ Met | Both sources; remove bumps version |
| Massive polls snapshot-all, ms→s timestamp (MASSIVE §2) | ✅ Met | `to_thread`, `/1000.0`, defensive per-ticker skip |
| Massive poll swallows errors, never kills loop (MASSIVE §5) | ✅ Met | Loop catches all non-`CancelledError` |
| `start()` seeds cache immediately (SIMULATOR §6) | ✅ Met | First SSE connection has data |
| `stop()` idempotent (INTERFACE §3) | ✅ Met | Guarded on `_task` done/None |
| Public re-exports via `app.market` (INTERFACE §9) | ✅ Met | `__init__.py` matches design |

### Partial / worth noting
- **SSE payload = full snapshot, not per-changed-ticker.** PLAN §6 says the server
  "pushes an event only for tickers whose price actually changed." The implementation
  pushes the **entire** price map whenever *any* ticker's version changes
  (`stream.py:44-46`). This is intentional per `MARKET_DATA_DESIGN.md §8` ("full
  snapshot per event … client replaces its price map entirely … safe for reconnection")
  and is a reasonable design, but it does technically diverge from the literal PLAN
  wording. No action needed beyond awareness — the frontend contract is "replace your
  whole map on each event."

---

## Issues Found

### 1. [MAJOR — test bug] `test_tsla_correlation_is_independent` asserts a mathematically false premise
**Location:** `tests/market/test_simulator.py` (the `test_tsla_correlation_is_independent` test, ~line 132)

The test asserts `cov_tech > cov_tsla`, expecting the AAPL/MSFT pair (ρ=0.6) to have
higher return covariance than the AAPL/TSLA pair (ρ=0.3). But covariance of returns is
`ρ · σ_a · σ_b · dt`, not ρ alone:

- AAPL/MSFT: `0.6 × 0.22 × 0.20 = 0.0264`
- AAPL/TSLA: `0.3 × 0.22 × 0.50 = 0.0330`

TSLA's volatility (σ=0.50) more than compensates for its lower correlation, so the
**TSLA pair has higher covariance in expectation**. The test fails deterministically
(observed 5/5). The implementation is correct — `_correlation()` returns `TSLA_CORR=0.3`
exactly as designed; only the test's assumption is wrong.

**Suggested fix:** Assert on the **correlation coefficient** instead of raw covariance —
normalize by the standard deviations, i.e. compare `cov / (σ_a·σ_b)`, or directly assert
that `sim._correlation("AAPL","TSLA") < sim._correlation("AAPL","MSFT")` (a `test_correlation_*`
unit test already covers the matrix directly and passes). The statistical version should
compare *Pearson correlation* of the return series, not covariance.

### 2. [MINOR] SimulatorDataSource reaches into engine private state
**Location:** `simulator.py:161` — `for ticker, price in self._engine._prices.items():`

`start()` reads the engine's private `_prices` dict to seed the cache. The engine already
exposes `get_tickers()` and `get_price()`; seeding via the public API
(`for t in engine.get_tickers(): cache.update(t, engine.get_price(t))`) would avoid the
encapsulation break. Cosmetic; behavior is correct.

### 3. [MINOR] Unknown tickers share the same `DEFAULT_PARAMS` dict object
**Location:** `simulator.py:101` — `params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)`

Every dynamically-added unknown ticker stores a reference to the *same* module-level
`DEFAULT_PARAMS` dict. It is only ever read, so this is harmless today, but if any code
ever mutates a ticker's params it would silently affect all unknown tickers. Defensive
fix: `dict(TICKER_PARAMS.get(ticker, DEFAULT_PARAMS))` to store a copy.

### 4. [MINOR] Unused import in `models.py`
**Location:** `models.py:2` — `from time import time` is never used in this module.
Harmless; remove for cleanliness.

### 5. [MINOR] No committed lockfile / test deps not reproducible
The base interpreter lacks `pytest`, and there is no `uv.lock`. CI and the Docker build
need a reproducible dependency set. Commit `uv.lock` (run `uv sync`) so
`uv run pytest` works deterministically everywhere.

### 6. [NIT] `cache.version` read without the lock
**Location:** `cache.py:13-14` (the `version` property) and `stream.py:41`

Reading the `int` without holding `_lock` is safe under CPython (int reads are atomic via
the GIL) and the worst case is reading a value one tick stale, which the next 500ms poll
corrects. Acceptable for this design; noting only for completeness.

### 7. [NIT] `_run_loop` re-checks `self._engine is None`
**Location:** `simulator.py:194` — the loop body guards `if self._engine is None: continue`,
but the task is only created in `start()` after `_engine` is assigned, so the guard is
effectively dead. Harmless defensiveness.

---

## Code Quality

**Strengths**
- Clean **math/lifecycle separation**: `GBMSimulator` is pure and synchronous,
  unit-testable without asyncio; `SimulatorDataSource` owns the async loop and cache I/O.
- **Source-agnostic downstream**: the factory is the only env-var branch; SSE and future
  consumers only know `PriceCache`.
- **Robust error handling** in both background loops: `CancelledError` re-raised, all other
  exceptions logged and swallowed so a transient fault never kills the producer task.
- **Defensive Massive parsing**: per-snapshot `try/except (AttributeError, TypeError)`
  means one bad ticker never poisons the batch; SDK exceptions return `[]`.
- **Lazy `massive` import** inside `start()`/`_fetch_snapshots()` keeps the simulator path
  (and tests) free of the SDK dependency; `conftest.py` stubs the module cleanly.
- **Numeric precision** matches PLAN §7: prices rounded to 2dp on cache write, change/%
  computed as properties (no stored staleness), 1-cent price floor.

**Minor smells** — items 2, 3, 4, 7 above; all cosmetic, none affect correctness.

---

## Test Coverage

**91 tests** across 7 files — coverage is genuinely thorough:
- **Cache:** versioning, first-update-flat, direction up/down, remove bumps version.
- **Models:** all three properties, zero-previous guard, frozen immutability, to_dict shape.
- **Simulator:** seed match, positivity (with and without events), add/remove + Cholesky
  rebuild validity, unknown-ticker defaults, price floor, correlation matrix per pair.
- **DataSource:** cache seeded on start, get/add/remove, idempotent stop, before-start no-ops.
- **Massive:** poll updates cache, ms→s conversion, bad-snapshot skip, empty-ticker no-op,
  SDK-exception → empty, idempotent stop, start calls poll once.
- **Factory:** all four env-var states, key plumbing, unstarted source.
- **Stream:** retry-first, emit-on-change, version-change trigger, disconnect break, router shape.

**Gaps worth closing**
- The correlation *statistical* test (#1) is the only behavioral test of co-movement and it
  is broken; fix it to actually validate that correlation flows through Cholesky.
- No test asserts the **full-snapshot** SSE payload includes *all* tickers when only one
  changed (the documented design) — would lock in the contract for the frontend.
- No concurrency/thread-safety test exercising simultaneous `update()` from a worker thread
  and `get_all()` from the loop (the whole reason for `threading.Lock`).
- `MassiveDataSource._poll_once` is tested with mocks; no test covers the real ms timestamp
  on the actual SDK model (acceptable — SDK is external).

---

## Conclusion

The market data component is **production-quality and ready to integrate**. It implements
every design decision in the planning docs, has a clean architecture that keeps the rest of
the platform agnostic to the data source, and is backed by a broad, mostly-correct test
suite (90/91 passing).

The single failing test is a **test defect, not a code defect** — it asserts that
correlation alone determines covariance, ignoring volatility, which is false for the
high-σ TSLA pair. Fixing that test (compare normalized correlation, or assert on the
correlation matrix directly) restores a green suite. The remaining findings are minor
cleanups (encapsulation, a shared dict reference, an unused import) and one infrastructure
gap (commit `uv.lock` for reproducible CI). None block downstream work on portfolio, trade
fills, or the SSE-driven frontend.

**Verdict:** ✅ Approved to build on, after fixing Issue #1 and committing a lockfile (#5).
