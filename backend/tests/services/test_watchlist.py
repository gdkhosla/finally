"""Unit tests for the watchlist service: add, remove, open-position rejection."""
import pytest

import app.db.connection as conn_module
from app.db import init_db, repo
from app.services.portfolio import execute_trade
from app.services.watchlist import add_ticker_to_watchlist, remove_ticker_from_watchlist
from app.state import price_cache


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", db_file)
    monkeypatch.setattr(conn_module, "DB_PATH", db_file)
    init_db()
    price_cache.update("AAPL", 100.0)
    yield


async def test_add_ticker():
    result = await add_ticker_to_watchlist("PYPL")
    assert result["ok"] is True
    assert repo.watchlist_has("PYPL") is True


async def test_remove_ticker():
    await add_ticker_to_watchlist("PYPL")
    result = await remove_ticker_from_watchlist("PYPL")
    assert result["ok"] is True
    assert repo.watchlist_has("PYPL") is False


async def test_remove_with_open_position_rejected():
    await execute_trade("AAPL", "buy", 1)
    result = await remove_ticker_from_watchlist("AAPL")
    assert result["ok"] is False
    assert repo.watchlist_has("AAPL") is True
