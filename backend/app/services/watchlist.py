"""Watchlist service — keeps DB state and the live market source in sync.

Both the watchlist route and the LLM chat handler call these, so the
watchlist<->market coupling lives here only.
"""
from app.db import repo
from app.state import market_source


async def add_ticker_to_watchlist(ticker: str) -> dict:
    """Add a ticker to the watchlist and start tracking its price."""
    ticker = ticker.upper()
    repo.add_watchlist(ticker)
    await market_source.add_ticker(ticker)
    return {"ok": True, "ticker": ticker}


async def remove_ticker_from_watchlist(ticker: str) -> dict:
    """Remove a ticker from the watchlist.

    Rejected if an open position exists; the user must close it first.
    """
    ticker = ticker.upper()
    if repo.get_position(ticker) is not None:
        return {"ok": False, "error": f"Cannot remove {ticker}: open position exists"}
    repo.remove_watchlist(ticker)
    await market_source.remove_ticker(ticker)
    return {"ok": True, "ticker": ticker}
