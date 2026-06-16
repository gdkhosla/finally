"""
Tests that both MarketDataSource implementations conform to the interface contract.
"""
import pytest
from unittest.mock import AsyncMock, patch

from app.market.interface import MarketDataSource
from app.market.cache import PriceCache
from app.market.simulator import SimulatorDataSource
from app.market.massive import MassiveDataSource


def test_simulator_is_subclass():
    assert issubclass(SimulatorDataSource, MarketDataSource)


def test_massive_is_subclass():
    assert issubclass(MassiveDataSource, MarketDataSource)


def test_simulator_has_all_abstract_methods():
    """SimulatorDataSource must implement every abstract method."""
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache)
    assert callable(src.start)
    assert callable(src.stop)
    assert callable(src.add_ticker)
    assert callable(src.remove_ticker)
    assert callable(src.get_tickers)


def test_massive_has_all_abstract_methods():
    """MassiveDataSource must implement every abstract method."""
    cache = PriceCache()
    src = MassiveDataSource(api_key="key", price_cache=cache)
    assert callable(src.start)
    assert callable(src.stop)
    assert callable(src.add_ticker)
    assert callable(src.remove_ticker)
    assert callable(src.get_tickers)


@pytest.mark.asyncio
async def test_simulator_stop_idempotent_after_start():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL"])
    await src.stop()
    await src.stop()


@pytest.mark.asyncio
async def test_simulator_add_remove_noop_before_start():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache)
    await src.add_ticker("AAPL")   # no-op before start
    await src.remove_ticker("AAPL")  # no-op before start


@pytest.mark.asyncio
async def test_massive_add_remove_noop_without_tickers():
    cache = PriceCache()
    src = MassiveDataSource(api_key="key", price_cache=cache)
    await src.add_ticker("AAPL")
    await src.remove_ticker("AAPL")
    assert "AAPL" not in src._tickers
