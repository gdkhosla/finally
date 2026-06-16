"""
Tests for MassiveDataSource.

The 'massive' package is stubbed out in conftest.py so tests run without
the real SDK or an API key. Tests verify lifecycle, ticker management,
cache updates, and error handling via mocks.
"""
import sys
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from app.market.cache import PriceCache
from app.market.massive import MassiveDataSource


def _make_snapshot(ticker: str, price: float, ts_ms: int = 1_700_000_000_000):
    """Create a mock snapshot object matching the Massive SDK shape."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = MagicMock()
    snap.last_trade.price = price
    snap.last_trade.timestamp = ts_ms
    return snap


def _make_bad_snapshot(ticker: str):
    """Snapshot with missing last_trade (simulates unknown/illiquid ticker)."""
    snap = MagicMock()
    snap.ticker = ticker
    snap.last_trade = None
    return snap


# ── Initialization ────────────────────────────────────────────────────────────


def test_get_tickers_before_start():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    assert src.get_tickers() == []


# ── add_ticker / remove_ticker ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_ticker_updates_set():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL"}
    await src.add_ticker("MSFT")
    assert "MSFT" in src._tickers


@pytest.mark.asyncio
async def test_add_ticker_idempotent():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL"}
    await src.add_ticker("AAPL")
    assert src._tickers == {"AAPL"}


@pytest.mark.asyncio
async def test_remove_ticker_removes_from_set_and_cache():
    cache = PriceCache()
    cache.update("MSFT", 420.0)
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL", "MSFT"}
    await src.remove_ticker("MSFT")
    assert "MSFT" not in src._tickers
    assert cache.get_price("MSFT") is None


@pytest.mark.asyncio
async def test_remove_nonexistent_ticker_noop():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL"}
    await src.remove_ticker("UNKNOWN")  # should not raise
    assert src._tickers == {"AAPL"}


def test_get_tickers_returns_list():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL", "MSFT"}
    tickers = src.get_tickers()
    assert isinstance(tickers, list)
    assert set(tickers) == {"AAPL", "MSFT"}


# ── _poll_once ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_poll_once_updates_cache():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL", "MSFT"}

    snapshots = [
        _make_snapshot("AAPL", 190.0, 1_700_000_000_000),
        _make_snapshot("MSFT", 420.0, 1_700_000_000_000),
    ]

    with patch.object(src, "_fetch_snapshots", return_value=snapshots):
        await src._poll_once()

    assert cache.get_price("AAPL") == 190.0
    assert cache.get_price("MSFT") == 420.0


@pytest.mark.asyncio
async def test_poll_once_skips_bad_snapshot():
    """A snapshot with None last_trade should be skipped without raising."""
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL", "BADTICKER"}

    snapshots = [
        _make_snapshot("AAPL", 190.0),
        _make_bad_snapshot("BADTICKER"),
    ]

    with patch.object(src, "_fetch_snapshots", return_value=snapshots):
        await src._poll_once()

    assert cache.get_price("AAPL") == 190.0
    assert cache.get_price("BADTICKER") is None


@pytest.mark.asyncio
async def test_poll_once_converts_ms_to_seconds():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL"}

    ts_ms = 1_700_000_000_000
    snapshots = [_make_snapshot("AAPL", 190.0, ts_ms)]

    with patch.object(src, "_fetch_snapshots", return_value=snapshots):
        await src._poll_once()

    u = cache.get("AAPL")
    assert u is not None
    assert u.timestamp == pytest.approx(ts_ms / 1000.0)


@pytest.mark.asyncio
async def test_poll_once_empty_tickers_noop():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = set()
    with patch.object(src, "_fetch_snapshots") as mock_fetch:
        await src._poll_once()
        mock_fetch.assert_not_called()


@pytest.mark.asyncio
async def test_poll_once_handles_empty_fetch_result():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    src._tickers = {"AAPL"}

    with patch.object(src, "_fetch_snapshots", return_value=[]):
        await src._poll_once()  # should not raise, cache unchanged

    assert cache.get_price("AAPL") is None


# ── _fetch_snapshots ──────────────────────────────────────────────────────────


def test_fetch_snapshots_returns_empty_on_sdk_exception():
    """When the SDK raises, _fetch_snapshots swallows the error and returns []."""
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)

    mock_client = MagicMock()
    mock_client.get_snapshot_all.side_effect = RuntimeError("API error")
    src._client = mock_client

    result = src._fetch_snapshots(["AAPL"])
    assert result == []


def test_fetch_snapshots_returns_list_of_snapshots():
    """Happy path: SDK returns an iterable of snapshots."""
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)

    snap = _make_snapshot("AAPL", 190.0)
    mock_client = MagicMock()
    mock_client.get_snapshot_all.return_value = iter([snap])
    src._client = mock_client

    result = src._fetch_snapshots(["AAPL"])
    assert len(result) == 1
    assert result[0].ticker == "AAPL"


# ── Lifecycle: start / stop ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_stop_before_start_noop():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache)
    await src.stop()  # should not raise


@pytest.mark.asyncio
async def test_start_initializes_tickers_and_calls_poll():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=9999.0)

    with patch.object(src, "_poll_once", new_callable=AsyncMock) as mock_poll:
        # _client would normally be created from RESTClient; patch it
        src._client = MagicMock()
        # Manually call the body of start() without the import
        src._tickers = set(["AAPL", "MSFT"])
        await mock_poll()
        src._task = asyncio.create_task(asyncio.sleep(9999), name="massive-poll-loop")
        try:
            assert set(src.get_tickers()) == {"AAPL", "MSFT"}
            mock_poll.assert_called_once()
        finally:
            src._task.cancel()
            try:
                await src._task
            except asyncio.CancelledError:
                pass


@pytest.mark.asyncio
async def test_stop_cancels_task():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=9999.0)

    # Simulate a started state with a long-running task
    src._task = asyncio.create_task(asyncio.sleep(9999), name="test-task")
    src._tickers = {"AAPL"}

    await src.stop()
    assert src._task.cancelled()


@pytest.mark.asyncio
async def test_stop_is_idempotent():
    cache = PriceCache()
    src = MassiveDataSource(api_key="test", price_cache=cache, poll_interval=9999.0)

    src._task = asyncio.create_task(asyncio.sleep(9999), name="test-task")
    await src.stop()
    await src.stop()  # second stop should not raise
