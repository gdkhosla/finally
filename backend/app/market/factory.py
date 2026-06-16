import os

from .cache import PriceCache
from .interface import MarketDataSource
from .massive import MassiveDataSource
from .simulator import SimulatorDataSource


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
