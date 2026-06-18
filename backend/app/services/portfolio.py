"""Portfolio service — trade execution and authoritative P&L.

Numeric precision per PLAN.md Section 7: money stored/returned full precision;
share quantity rounded to 4 dp on trade entry. P&L is computed here and is the
single source of truth.
"""
from app.db import repo
from app.state import market_source, price_cache


def _round_qty(quantity: float) -> float:
    return round(quantity, 4)


async def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Execute a market order. Returns a result dict; never raises on validation.

    {"ok": True, "trade": {...}, "fill_price": float}
    {"ok": False, "error": "reason"}
    """
    ticker = ticker.upper()
    side = side.lower()

    if side not in ("buy", "sell"):
        return {"ok": False, "error": f"Invalid side: {side}"}

    quantity = _round_qty(quantity)
    if quantity <= 0:
        return {"ok": False, "error": "Quantity must be positive"}

    # Auto-add untracked ticker so a fill price exists.
    if not repo.watchlist_has(ticker):
        repo.add_watchlist(ticker)
        await market_source.add_ticker(ticker)

    fill_price = price_cache.get_price(ticker)
    if fill_price is None:
        return {"ok": False, "error": f"No price available for {ticker}"}

    profile = repo.get_profile()
    cash = profile["cash_balance"]
    position = repo.get_position(ticker)
    cost = quantity * fill_price

    if side == "buy":
        if cash < cost:
            return {"ok": False, "error": "Insufficient cash"}
        if position:
            old_qty = position["quantity"]
            new_qty = _round_qty(old_qty + quantity)
            new_avg = (old_qty * position["avg_cost"] + quantity * fill_price) / new_qty
        else:
            new_qty = quantity
            new_avg = fill_price
        repo.upsert_position(ticker, new_qty, new_avg)
        repo.set_cash(cash - cost)
    else:  # sell
        if not position or position["quantity"] < quantity:
            return {"ok": False, "error": "Insufficient shares"}
        new_qty = _round_qty(position["quantity"] - quantity)
        if new_qty == 0:
            repo.delete_position(ticker)
        else:
            repo.upsert_position(ticker, new_qty, position["avg_cost"])
        repo.set_cash(cash + cost)

    trade = repo.record_trade(ticker, side, quantity, fill_price)
    repo.record_snapshot(get_portfolio()["total_value"])
    return {"ok": True, "trade": trade, "fill_price": fill_price}


def get_portfolio() -> dict:
    """Return cash, positions with live P&L, total value, and total unrealized P&L."""
    profile = repo.get_profile()
    cash = profile["cash_balance"]

    positions = []
    total_unrealized = 0.0
    holdings_value = 0.0
    for pos in repo.list_positions():
        ticker = pos["ticker"]
        qty = pos["quantity"]
        avg_cost = pos["avg_cost"]
        current_price = price_cache.get_price(ticker)
        if current_price is None:
            current_price = avg_cost
        market_value = qty * current_price
        unrealized = qty * (current_price - avg_cost)
        pct_change = ((current_price - avg_cost) / avg_cost * 100) if avg_cost else 0.0
        holdings_value += market_value
        total_unrealized += unrealized
        positions.append(
            {
                "ticker": ticker,
                "quantity": qty,
                "avg_cost": avg_cost,
                "current_price": current_price,
                "unrealized_pnl": unrealized,
                "pct_change": pct_change,
            }
        )

    return {
        "cash_balance": cash,
        "positions": positions,
        "total_value": cash + holdings_value,
        "unrealized_pnl": total_unrealized,
    }
