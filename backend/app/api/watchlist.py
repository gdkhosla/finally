"""Watchlist routes — list tickers with live prices, add, remove."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db import repo
from app.services.watchlist import add_ticker_to_watchlist, remove_ticker_from_watchlist
from app.state import price_cache

router = APIRouter(prefix="/api/watchlist")


class WatchlistRequest(BaseModel):
    ticker: str


@router.get("")
async def watchlist() -> dict:
    tickers = []
    for ticker in repo.list_watchlist():
        update = price_cache.get(ticker)
        if update:
            tickers.append(
                {
                    "ticker": ticker,
                    "price": update.price,
                    "previous_price": update.previous_price,
                    "change": update.change,
                    "change_percent": update.change_percent,
                    "direction": update.direction,
                }
            )
        else:
            tickers.append(
                {
                    "ticker": ticker,
                    "price": None,
                    "previous_price": None,
                    "change": None,
                    "change_percent": None,
                    "direction": None,
                }
            )
    return {"tickers": tickers}


@router.post("")
async def add(req: WatchlistRequest) -> dict:
    result = await add_ticker_to_watchlist(req.ticker)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}


@router.delete("/{ticker}")
async def remove(ticker: str) -> dict:
    result = await remove_ticker_from_watchlist(ticker)
    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"ok": True}
