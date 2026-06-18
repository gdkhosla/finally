"""Route tests via FastAPI TestClient: status codes and response shapes."""
import pytest
from fastapi.testclient import TestClient

import app.db.connection as conn_module
from app.main import app
from app.state import price_cache


@pytest.fixture
def client(tmp_path, monkeypatch):
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", db_file)
    monkeypatch.setattr(conn_module, "DB_PATH", db_file)
    with TestClient(app) as c:
        # Override simulator-seeded prices with deterministic values.
        price_cache.update("AAPL", 100.0)
        yield c


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_portfolio_shape(client):
    r = client.get("/api/portfolio")
    assert r.status_code == 200
    body = r.json()
    assert set(body) == {"cash_balance", "positions", "total_value", "unrealized_pnl"}
    assert body["cash_balance"] == 10000.0


def test_trade_buy_success(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 5, "side": "buy"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["fill_price"] == 100.0


def test_trade_insufficient_cash_400(client):
    r = client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1000, "side": "buy"})
    assert r.status_code == 400


def test_history_shape(client):
    r = client.get("/api/portfolio/history")
    assert r.status_code == 200
    assert "snapshots" in r.json()


def test_watchlist_shape(client):
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    tickers = r.json()["tickers"]
    assert any(t["ticker"] == "AAPL" for t in tickers)
    aapl = next(t for t in tickers if t["ticker"] == "AAPL")
    assert set(aapl) == {"ticker", "price", "previous_price", "change", "change_percent", "direction"}


def test_watchlist_add_and_remove(client):
    price_cache.update("PYPL", 50.0)
    r = client.post("/api/watchlist", json={"ticker": "PYPL"})
    assert r.status_code == 200
    r = client.delete("/api/watchlist/PYPL")
    assert r.status_code == 200


def test_watchlist_remove_open_position_400(client):
    client.post("/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"})
    r = client.delete("/api/watchlist/AAPL")
    assert r.status_code == 400
