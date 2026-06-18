"""Module-level singletons shared by services and routes.

Importing the price cache and market source from here (rather than from
``app.main``) avoids circular imports. The market source is returned unstarted;
``app.main`` owns starting and stopping it in the FastAPI lifespan.
"""
from app.market import PriceCache, create_market_data_source

price_cache = PriceCache()
market_source = create_market_data_source(price_cache)
