import os
import pytest
from unittest.mock import patch

from app.market.cache import PriceCache
from app.market.factory import create_market_data_source
from app.market.simulator import SimulatorDataSource
from app.market.massive import MassiveDataSource


def test_factory_returns_simulator_when_no_key():
    cache = PriceCache()
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        src = create_market_data_source(cache)
    assert isinstance(src, SimulatorDataSource)


def test_factory_returns_simulator_when_key_empty():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": ""}):
        src = create_market_data_source(cache)
    assert isinstance(src, SimulatorDataSource)


def test_factory_returns_simulator_when_key_whitespace():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "   "}):
        src = create_market_data_source(cache)
    assert isinstance(src, SimulatorDataSource)


def test_factory_returns_massive_when_key_set():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "my-real-key"}):
        src = create_market_data_source(cache)
    assert isinstance(src, MassiveDataSource)


def test_factory_massive_gets_correct_key():
    cache = PriceCache()
    with patch.dict(os.environ, {"MASSIVE_API_KEY": "secret-key-123"}):
        src = create_market_data_source(cache)
    assert isinstance(src, MassiveDataSource)
    assert src._api_key == "secret-key-123"


def test_factory_returns_unstarted_source():
    cache = PriceCache()
    with patch.dict(os.environ, {}, clear=True):
        os.environ.pop("MASSIVE_API_KEY", None)
        src = create_market_data_source(cache)
    # An unstarted SimulatorDataSource should have no engine
    assert isinstance(src, SimulatorDataSource)
    assert src._engine is None
    assert src._task is None
