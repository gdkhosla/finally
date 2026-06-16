# Market Data Component — Code Review

**Date:** 2026-06-16
**Reviewer:** Automated code review agent
**Component:** `backend/app/market/` and `backend/tests/market/`
**Verdict:** Ready to integrate with minor fixes required (Issues 1 and 2 are blocking)

---

## Executive Summary

The market data component is well-implemented and closely matches the design specification. All seven source files (`models.py`, `cache.py`, `interface.py`, `seed_prices.py`, `simulator.py`, `massive.py`, `factory.py`) and the SSE router (`stream.py`) are present and correctly implement the design in `MARKET_DATA_DESIGN.md`. The test suite has 91 tests with 90 passing and 1 failing.

The failing test (`test_tsla_correlation_is_independent`) exposes a mathematically incorrect assertion in the test — not a bug in the implementation. The other notable issue is a missing `pyproject.toml` hatch build section that prevents `uv run` from working. Both should be fixed before downstream agents begin integrating.

**Bottom line: The market data subsystem is production-quality and ready for integration after fixing the two issues below.**

---

## Test Results

**Run command:** `cd /home/user/finally/backend && PYTHONPATH=/home/user/finally/backend .venv/bin/python -m pytest tests/ -v`

Note: `uv run python -m pytest` fails due to missing hatch build config (Issue 1). Tests were run by activating the venv directly after `uv sync --no-install-project`.

```
============================= test session starts ==============================
platform linux -- Python 3.12.3, pytest-9.1.0, pluggy-1.6.0
asyncio: mode=Mode.AUTO
collected 91 items

tests/market/test_cache.py::test_version_starts_at_zero PASSED
tests/market/test_cache.py::test_update_bumps_version PASSED
tests/market/test_cache.py::test_update_bumps_version_each_time PASSED
tests/market/test_cache.py::test_first_update_flat_direction PASSED
tests/market/test_cache.py::test_second_update_shows_direction PASSED
tests/market/test_cache.py::test_price_rounded_to_2dp PASSED
tests/market/test_cache.py::test_get_returns_latest PASSED
tests/market/test_cache.py::test_get_nonexistent_returns_none PASSED
tests/market/test_cache.py::test_get_price_returns_float PASSED
tests/market/test_cache.py::test_get_price_nonexistent_returns_none PASSED
tests/market/test_cache.py::test_get_all_returns_all_tickers PASSED
tests/market/test_cache.py::test_get_all_returns_copy PASSED
tests/market/test_cache.py::test_remove_ticker PASSED
tests/market/test_cache.py::test_remove_bumps_version PASSED
tests/market/test_cache.py::test_remove_nonexistent_does_not_raise PASSED
tests/market/test_cache.py::test_timestamp_used_when_provided PASSED
tests/market/test_cache.py::test_concurrent_updates_thread_safe PASSED
tests/market/test_factory.py::test_factory_returns_simulator_when_no_key PASSED
tests/market/test_factory.py::test_factory_returns_simulator_when_key_empty PASSED
tests/market/test_factory.py::test_factory_returns_simulator_when_key_whitespace PASSED
tests/market/test_factory.py::test_factory_returns_massive_when_key_set PASSED
tests/market/test_factory.py::test_factory_massive_gets_correct_key PASSED
tests/market/test_factory.py::test_factory_returns_unstarted_source PASSED
tests/market/test_interface.py::test_simulator_is_subclass PASSED
tests/market/test_interface.py::test_massive_is_subclass PASSED
tests/market/test_interface.py::test_simulator_has_all_abstract_methods PASSED
tests/market/test_interface.py::test_massive_has_all_abstract_methods PASSED
tests/market/test_interface.py::test_simulator_stop_idempotent_after_start PASSED
tests/market/test_interface.py::test_simulator_add_remove_noop_before_start PASSED
tests/market/test_interface.py::test_massive_add_remove_noop_without_tickers PASSED
tests/market/test_massive.py::test_get_tickers_before_start PASSED
tests/market/test_massive.py::test_add_ticker_updates_set PASSED
tests/market/test_massive.py::test_add_ticker_idempotent PASSED
tests/market/test_massive.py::test_remove_ticker_removes_from_set_and_cache PASSED
tests/market/test_massive.py::test_remove_nonexistent_ticker_noop PASSED
tests/market/test_massive.py::test_get_tickers_returns_list PASSED
tests/market/test_massive.py::test_poll_once_updates_cache PASSED
tests/market/test_massive.py::test_poll_once_skips_bad_snapshot PASSED
tests/market/test_massive.py::test_poll_once_converts_ms_to_seconds PASSED
tests/market/test_massive.py::test_poll_once_empty_tickers_noop PASSED
tests/market/test_massive.py::test_poll_once_handles_empty_fetch_result PASSED
tests/market/test_massive.py::test_fetch_snapshots_returns_empty_on_sdk_exception PASSED
tests/market/test_massive.py::test_fetch_snapshots_returns_list_of_snapshots PASSED
tests/market/test_massive.py::test_stop_before_start_noop PASSED
tests/market/test_massive.py::test_start_initializes_tickers_and_calls_poll PASSED
tests/market/test_massive.py::test_stop_cancels_task PASSED
tests/market/test_massive.py::test_stop_is_idempotent PASSED
tests/market/test_models.py::test_price_update_direction_up PASSED
tests/market/test_models.py::test_price_update_direction_down PASSED
tests/market/test_models.py::test_price_update_direction_flat PASSED
tests/market/test_models.py::test_price_update_change PASSED
tests/market/test_models.py::test_price_update_change_negative PASSED
tests/market/test_models.py::test_price_update_change_percent PASSED
tests/market/test_models.py::test_price_update_change_percent_zero_previous PASSED
tests/market/test_models.py::test_price_update_to_dict_keys PASSED
tests/market/test_models.py::test_price_update_to_dict_values PASSED
tests/market/test_models.py::test_price_update_is_frozen PASSED
tests/market/test_simulator.py::test_initial_prices_match_seed PASSED
tests/market/test_simulator.py::test_get_tickers_returns_all PASSED
tests/market/test_simulator.py::test_step_returns_all_tickers PASSED
tests/market/test_simulator.py::test_prices_always_positive PASSED
tests/market/test_simulator.py::test_prices_positive_with_events PASSED
tests/market/test_simulator.py::test_step_empty_tickers_returns_empty PASSED
tests/market/test_simulator.py::test_add_ticker_appears_in_step PASSED
tests/market/test_simulator.py::test_add_existing_ticker_is_noop PASSED
tests/market/test_simulator.py::test_remove_ticker_disappears_from_step PASSED
tests/market/test_simulator.py::test_remove_nonexistent_ticker_noop PASSED
tests/market/test_simulator.py::test_add_remove_rebuilds_cholesky PASSED
tests/market/test_simulator.py::test_unknown_ticker_gets_default_seed PASSED
tests/market/test_simulator.py::test_correlated_tickers_positive_covariance PASSED
tests/market/test_simulator.py::test_tsla_correlation_is_independent FAILED   ← See Issue #1
tests/market/test_simulator.py::test_price_floor_at_one_cent PASSED
tests/market/test_simulator.py::test_correlation_tech_tech PASSED
tests/market/test_simulator.py::test_correlation_finance_finance PASSED
tests/market/test_simulator.py::test_correlation_cross_group PASSED
tests/market/test_simulator.py::test_correlation_tsla PASSED
tests/market/test_simulator.py::test_cholesky_valid_after_add PASSED
tests/market/test_simulator.py::test_simulator_data_source_seeds_cache PASSED
tests/market/test_simulator.py::test_simulator_data_source_get_tickers PASSED
tests/market/test_simulator.py::test_simulator_data_source_add_ticker PASSED
tests/market/test_simulator.py::test_simulator_data_source_remove_ticker PASSED
tests/market/test_simulator.py::test_simulator_data_source_stop_is_idempotent PASSED
tests/market/test_simulator.py::test_simulator_data_source_get_tickers_before_start PASSED
tests/market/test_simulator.py::test_simulator_data_source_add_ticker_before_start_noop PASSED
tests/market/test_simulator.py::test_simulator_data_source_updates_cache_on_tick PASSED
tests/market/test_stream.py::test_price_generator_emits_retry_first PASSED
tests/market/test_stream.py::test_price_generator_emits_price_data PASSED
tests/market/test_stream.py::test_price_generator_stops_on_disconnect PASSED
tests/market/test_stream.py::test_price_generator_emits_on_version_change PASSED
tests/market/test_stream.py::test_create_stream_router_returns_api_router PASSED
tests/market/test_stream.py::test_stream_router_has_prices_route PASSED

=================================== FAILURES ===================================
FAILED tests/market/test_simulator.py::test_tsla_correlation_is_independent
  AssertionError: Tech-tech covariance should exceed TSLA pair covariance
  assert 2.2492001829389632e-09 > 3.47610543583032e-09

========================= 1 failed, 90 passed in 2.16s =========================
```

---

## Spec Compliance

Checked against `planning/PLAN.md` Section 6 (Market Data) and `planning/MARKET_DATA_DESIGN.md`.

| Requirement | Status | Notes |
|---|---|---|
| GBM with configurable drift/volatility per ticker | PASS | `simulator.py` `GBMSimulator`; `seed_prices.py` `TICKER_PARAMS` |
| Updates at ~500ms intervals | PASS | `DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR`; loop interval = 0.5s |
| Correlated moves across tickers via Cholesky | PASS | `simulator.py:44-66`; correlation matrix rebuilt on membership change |
| Occasional random events (2-5% spikes, 0.1% probability) | PASS | `simulator.py:58-61` |
| Realistic seed prices, authoritative in `seed_prices.py` | PASS | 10 tickers with exact values; PLAN.md notes them as illustrative only |
| Massive API: REST polling, same interface as simulator | PASS | `massive.py` implements `MarketDataSource` ABC |
| Shared price cache: latest price, previous price, timestamp | PASS | `cache.py` stores `PriceUpdate` (frozen dataclass) per ticker |
| SSE endpoint `GET /api/stream/prices` | PASS | `stream.py` `create_stream_router` |
| Version-based change detection, emits only on change | PASS | `stream.py:33-42` — version integer compared per poll cycle |
| SSE events contain ticker, price, previous_price, timestamp, direction | PASS | `models.py` `PriceUpdate.to_dict()` includes all required fields |
| Abstract interface both implementations conform to | PASS | `interface.py` ABC; `test_interface.py` verifies conformance |
| Unknown tickers get default GBM params | PASS | `simulator.py:94-99` uses `DEFAULT_PARAMS` and random seed in [50, 300] |
| Factory reads `MASSIVE_API_KEY`, strips whitespace | PASS | `factory.py:13` |
| `massive` import deferred to `start()` to allow tests without SDK | PASS | `massive.py:30` |
| Cache seeded immediately at `start()` for first SSE connection | PASS | `simulator.py:147-149` |

**One design decision worth noting:** The spec says "pushes an event only for tickers whose price actually changed." The implementation pushes the **entire price map** whenever *any* ticker changes version. This is intentional per `MARKET_DATA_DESIGN.md §8` ("full snapshot per event — client replaces its price map entirely") and is the correct design for reconnect safety. It is a deliberate simplification beyond the literal PLAN wording.

---

## Code Quality

### Structure and Readability

The code is clean and well-structured with clear module responsibilities: pure math in `GBMSimulator`, async lifecycle in `SimulatorDataSource`, external API polling in `MassiveDataSource`, thread-safe data store in `PriceCache`, immutable data model in `PriceUpdate`. Inline comments are concise and accurate.

### Correctness

**GBM formula** (`simulator.py:51-53`): Correctly implements the Ito-correct discrete GBM step with Ito drift correction:
```python
drift = (mu - 0.5 * sigma ** 2) * dt
diffusion = sigma * math.sqrt(dt) * z_corr[i]
new_price = p * math.exp(drift + diffusion)
```

**Cholesky correlations** (`simulator.py:104-117`): Correlation matrix is built correctly as symmetric PD matrix with jitter fallback for edge cases. The `_correlation()` function handles TSLA as a special case correctly.

**Thread safety** (`cache.py`): `threading.Lock` is correct over `asyncio.Lock` because `MassiveDataSource._fetch_snapshots` runs in a worker thread via `asyncio.to_thread`.

**First-update semantics** (`cache.py:20`): `previous_price = price` on first update gives `direction == "flat"` — correct per spec.

**Massive timestamp conversion** (`massive.py:51`): Correctly divides milliseconds by 1000 to get seconds.

### Error Handling

- `simulator.py:_run_loop` catches all non-`CancelledError` exceptions and logs — tick errors never kill the background loop.
- `massive.py:_fetch_snapshots` catches all SDK exceptions and returns `[]`; per-snapshot `AttributeError`/`TypeError` is handled individually so one bad ticker never poisons the batch.
- Both `stop()` methods correctly re-raise `CancelledError` after cancellation.

### Edge Cases Handled

- Empty ticker list in `GBMSimulator.step()` returns `{}`.
- `SimulatorDataSource.add_ticker`/`remove_ticker` guard against `self._engine is None` (before `start()`).
- `PriceCache.remove()` on non-existent key handled silently via `dict.pop(key, None)`.
- Price floor at `0.01` prevents zero or negative prices (`simulator.py:62`).

---

## Test Coverage

### What Is Tested (91 tests)

| Module | Test File | Tests | Key Scenarios |
|---|---|---|---|
| `models.py` | `test_models.py` | 10 | All directions, change/%, to_dict keys+values, frozen |
| `cache.py` | `test_cache.py` | 17 | Versioning, first-update flat, direction, rounding, get/remove, thread safety |
| `interface.py` | `test_interface.py` | 7 | Subclass checks, callable methods, idempotent stop |
| `simulator.py` | `test_simulator.py` | 28 | GBM math, correlations, Cholesky, add/remove, async lifecycle, tick updates |
| `massive.py` | `test_massive.py` | 16 | Ticker management, poll_once, timestamp conversion, error handling, lifecycle |
| `factory.py` | `test_factory.py` | 6 | All key variants (empty/whitespace/set), correct type, unstarted state |
| `stream.py` | `test_stream.py` | 6 | Retry header, data emission, disconnect handling, router structure |

### Gaps Worth Noting

1. No integration test sends an HTTP request to the FastAPI route and reads the SSE stream (would require `httpx.AsyncClient` with streaming).
2. No test asserts the full-snapshot SSE payload includes all tickers when only one changed — this would lock in the contract for the frontend.
3. `MassiveDataSource.start()` integration is not tested end-to-end (the test for `start_initializes_tickers` manually replicates the logic rather than calling `src.start()`).
4. The one statistical behavioral test of co-movement (`test_tsla_correlation_is_independent`) is broken — the correlation matrix direct tests (`test_correlation_*`) are passing and are better coverage anyway.

---

## Issues Found

### Issue 1 — MAJOR: Flaky test with mathematically incorrect premise

**File:** `backend/tests/market/test_simulator.py`, lines 107-132 (`test_tsla_correlation_is_independent`)
**Severity:** Major (CI blocker — test fails)

The test asserts `cov_tech > cov_tsla`, expecting the AAPL/MSFT pair (ρ=0.6) to show higher return covariance than AAPL/TSLA (ρ=0.3). However, return covariance is `ρ · σ_a · σ_b · dt`, not ρ alone:

- AAPL/MSFT: `0.6 × 0.22 × 0.20 = 0.0264`
- AAPL/TSLA: `0.3 × 0.22 × 0.50 = 0.0330`

TSLA's high volatility (σ=0.50) more than compensates for its lower correlation coefficient, so the TSLA pair has **higher expected covariance**. The test fails deterministically. The implementation is correct — the bug is in the test.

**Suggested fix:** Replace the covariance comparison with a direct assertion on the correlation matrix (which already has passing unit tests for the exact values):

```python
def test_tsla_correlation_is_independent():
    """TSLA vs AAPL should have lower configured rho than AAPL vs MSFT."""
    sim = GBMSimulator(["AAPL", "MSFT", "TSLA"])
    rho_tech = sim._correlation("AAPL", "MSFT")   # 0.6
    rho_tsla = sim._correlation("AAPL", "TSLA")   # 0.3
    assert rho_tech > rho_tsla
```

---

### Issue 2 — MAJOR: `pyproject.toml` missing hatch build configuration

**File:** `backend/pyproject.toml`
**Severity:** Major (blocks `uv run` commands; CI will fail)

Hatchling cannot determine which directory to ship because the project name `finally-backend` does not match any directory. Running `uv run python -m pytest` or `uv sync` without `--no-install-project` fails with:

```
ValueError: Unable to determine which files to ship inside the wheel
```

**Suggested fix:** Add to `backend/pyproject.toml`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

This tells hatchling that the `app/` directory is the package to install, matching the import paths used throughout (`from app.market import ...`).

---

### Issue 3 — MINOR: `SimulatorDataSource` accesses private attribute `_prices`

**File:** `backend/app/market/simulator.py`, line 147
**Severity:** Minor (encapsulation)

```python
for ticker, price in self._engine._prices.items():
    self._cache.update(ticker, price)
```

`start()` reads the engine's private `_prices` dict. The engine already exposes `get_tickers()` and `get_price()`. Accessing private state is acceptable within the same file/module but creates a hidden coupling.

**Suggested fix:** Add `get_all_prices()` to `GBMSimulator` and use it:

```python
def get_all_prices(self) -> dict[str, float]:
    return dict(self._prices)
```

---

### Issue 4 — MINOR: Unknown tickers share the same `DEFAULT_PARAMS` dict object

**File:** `backend/app/market/simulator.py`, line 101
**Severity:** Minor (shared mutable reference)

```python
params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
```

Every dynamically-added unknown ticker stores a reference to the same module-level `DEFAULT_PARAMS` dict. Today it is only read, but any future code mutating a ticker's params would silently affect all unknown tickers.

**Suggested fix:** Store a copy: `params = dict(TICKER_PARAMS.get(ticker, DEFAULT_PARAMS))`

---

### Issue 5 — MINOR: Unused `time` import in `models.py`

**File:** `backend/app/market/models.py`, line 2
**Severity:** Nit

`from time import time` is imported but never used in `models.py`. Remove for cleanliness.

---

### Issue 6 — NIT: `cache.version` property reads without lock

**File:** `backend/app/market/cache.py`, lines 13-14
**Severity:** Nit (acceptable under CPython GIL)

The `version` property reads `self._version` without acquiring `_lock`. Under CPython this is safe (integer reads are atomic via the GIL) and the worst case is reading a value one tick stale, which the next 500ms SSE poll corrects. Not a bug, noting for completeness.

---

### Issue 7 — NIT: Dead guard in `_run_loop`

**File:** `backend/app/market/simulator.py`, line 194
**Severity:** Nit

```python
if self._engine is None:
    continue
```

This guard inside `_run_loop` is unreachable: the task is only created in `start()` after `_engine` is assigned, so `_engine` cannot be `None` while the loop is running. Harmless defensiveness.

---

## Conclusion

The market data component is **production-quality and ready to integrate**. It faithfully implements every requirement from `PLAN.md` and `MARKET_DATA_DESIGN.md`, has a clean architecture that keeps downstream consumers (portfolio, trade, LLM routes) agnostic to the price source, and is backed by a broad test suite (90/91 passing).

The single failing test is a **test defect, not an implementation defect** — it asserts that correlation coefficient alone determines covariance, which is incorrect when the two pairs have substantially different volatilities. Replacing the covariance comparison with a direct correlation-matrix assertion restores a green suite. The `pyproject.toml` build config gap is a developer-experience issue that must be fixed for CI and `uv run` to work.

**Recommended actions before downstream integration:**
1. Fix `test_tsla_correlation_is_independent` (Issue 1) — replace covariance assertion with direct `_correlation()` assertion.
2. Add `[tool.hatch.build.targets.wheel] packages = ["app"]` to `backend/pyproject.toml` (Issue 2).

**Optional cleanups (not blocking):**
- Add `get_all_prices()` public method to `GBMSimulator` (Issue 3).
- Copy `DEFAULT_PARAMS` on store (Issue 4).
- Remove unused `time` import from `models.py` (Issue 5).
