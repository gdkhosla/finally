"""Unit tests for the portfolio service: trade execution and P&L math."""
import pytest

import app.db.connection as conn_module
from app.db import init_db, repo
from app.services.portfolio import execute_trade, get_portfolio
from app.state import price_cache


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", db_file)
    monkeypatch.setattr(conn_module, "DB_PATH", db_file)
    init_db()
    # Deterministic prices for the seeded tickers used in tests.
    price_cache.update("AAPL", 100.0)
    price_cache.update("MSFT", 200.0)
    yield


async def test_buy_creates_position_and_debits_cash():
    result = await execute_trade("AAPL", "buy", 10)
    assert result["ok"] is True
    assert result["fill_price"] == 100.0
    pos = repo.get_position("AAPL")
    assert pos["quantity"] == 10
    assert pos["avg_cost"] == 100.0
    assert repo.get_profile()["cash_balance"] == 10000.0 - 1000.0


async def test_buy_weighted_avg_cost():
    await execute_trade("AAPL", "buy", 10)  # @100
    price_cache.update("AAPL", 200.0)
    await execute_trade("AAPL", "buy", 10)  # @200
    pos = repo.get_position("AAPL")
    assert pos["quantity"] == 20
    assert pos["avg_cost"] == 150.0


async def test_sell_reduces_position_and_credits_cash():
    await execute_trade("AAPL", "buy", 10)
    result = await execute_trade("AAPL", "sell", 4)
    assert result["ok"] is True
    pos = repo.get_position("AAPL")
    assert pos["quantity"] == 6
    assert repo.get_profile()["cash_balance"] == 10000.0 - 1000.0 + 400.0


async def test_full_sell_deletes_row():
    await execute_trade("AAPL", "buy", 10)
    await execute_trade("AAPL", "sell", 10)
    assert repo.get_position("AAPL") is None


async def test_insufficient_cash_rejected():
    result = await execute_trade("AAPL", "buy", 1000)  # 100k > 10k
    assert result["ok"] is False
    assert "cash" in result["error"].lower()
    assert repo.get_position("AAPL") is None


async def test_oversell_rejected():
    await execute_trade("AAPL", "buy", 5)
    result = await execute_trade("AAPL", "sell", 10)
    assert result["ok"] is False
    assert "shares" in result["error"].lower()


async def test_zero_quantity_rejected():
    result = await execute_trade("AAPL", "buy", 0)
    assert result["ok"] is False


async def test_auto_add_untracked_ticker():
    # Ticker not seeded in DB watchlist; pre-seed its price so a fill exists.
    price_cache.update("PYPL", 50.0)
    assert repo.watchlist_has("PYPL") is False
    result = await execute_trade("PYPL", "buy", 2)
    assert result["ok"] is True
    assert repo.watchlist_has("PYPL") is True


async def test_get_portfolio_math():
    await execute_trade("AAPL", "buy", 10)  # cost 1000 @100
    price_cache.update("AAPL", 120.0)
    p = get_portfolio()
    assert p["cash_balance"] == 9000.0
    assert len(p["positions"]) == 1
    pos = p["positions"][0]
    assert pos["current_price"] == 120.0
    assert pos["unrealized_pnl"] == pytest.approx(200.0)
    assert pos["pct_change"] == pytest.approx(20.0)
    assert p["total_value"] == pytest.approx(9000.0 + 10 * 120.0)
    assert p["unrealized_pnl"] == pytest.approx(200.0)
