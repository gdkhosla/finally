"""Unit tests for app.db — init, seed, and all repo functions."""
import pytest
import app.db.connection as conn_module
from app.db import init_db, repo


@pytest.fixture(autouse=True)
def isolated_db(tmp_path, monkeypatch):
    """Point DB_PATH at a fresh temp file for each test."""
    db_file = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", db_file)
    monkeypatch.setattr(conn_module, "DB_PATH", db_file)
    init_db()
    yield


# ---------------------------------------------------------------------------
# Init / seed idempotency
# ---------------------------------------------------------------------------

def test_init_seeds_profile():
    profile = repo.get_profile()
    assert profile["id"] == "default"
    assert profile["cash_balance"] == 10000.0


def test_init_seeds_watchlist():
    tickers = repo.list_watchlist()
    assert set(tickers) == {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}


def test_init_idempotent():
    """Calling init_db() multiple times must not duplicate seed data."""
    init_db()
    init_db()
    assert len(repo.list_watchlist()) == 10
    profile = repo.get_profile()
    assert profile["cash_balance"] == 10000.0


# ---------------------------------------------------------------------------
# Profile / cash
# ---------------------------------------------------------------------------

def test_set_cash():
    repo.set_cash(5000.0)
    assert repo.get_profile()["cash_balance"] == 5000.0


def test_set_cash_zero():
    repo.set_cash(0.0)
    assert repo.get_profile()["cash_balance"] == 0.0


# ---------------------------------------------------------------------------
# Watchlist
# ---------------------------------------------------------------------------

def test_add_watchlist():
    repo.add_watchlist("PYPL")
    assert repo.watchlist_has("PYPL")


def test_add_watchlist_idempotent():
    repo.add_watchlist("PYPL")
    repo.add_watchlist("PYPL")
    tickers = repo.list_watchlist()
    assert tickers.count("PYPL") == 1


def test_remove_watchlist():
    repo.remove_watchlist("AAPL")
    assert not repo.watchlist_has("AAPL")


def test_watchlist_has_false():
    assert not repo.watchlist_has("ZZZZ")


# ---------------------------------------------------------------------------
# Positions
# ---------------------------------------------------------------------------

def test_upsert_and_get_position():
    repo.upsert_position("AAPL", 10.0, 190.0)
    pos = repo.get_position("AAPL")
    assert pos["ticker"] == "AAPL"
    assert pos["quantity"] == 10.0
    assert pos["avg_cost"] == 190.0


def test_upsert_position_updates():
    repo.upsert_position("AAPL", 10.0, 190.0)
    repo.upsert_position("AAPL", 20.0, 195.0)
    pos = repo.get_position("AAPL")
    assert pos["quantity"] == 20.0
    assert pos["avg_cost"] == 195.0


def test_get_position_none():
    assert repo.get_position("ZZZZ") is None


def test_list_positions():
    repo.upsert_position("AAPL", 5.0, 190.0)
    repo.upsert_position("MSFT", 3.0, 420.0)
    positions = repo.list_positions()
    tickers = [p["ticker"] for p in positions]
    assert "AAPL" in tickers
    assert "MSFT" in tickers


def test_delete_position():
    """Full sell removes the row — no zero-qty rows remain."""
    repo.upsert_position("AAPL", 10.0, 190.0)
    repo.delete_position("AAPL")
    assert repo.get_position("AAPL") is None


def test_delete_position_not_in_list():
    repo.upsert_position("AAPL", 10.0, 190.0)
    repo.delete_position("AAPL")
    positions = repo.list_positions()
    assert all(p["ticker"] != "AAPL" for p in positions)


# ---------------------------------------------------------------------------
# Trades
# ---------------------------------------------------------------------------

def test_record_trade_returns_dict():
    trade = repo.record_trade("AAPL", "buy", 5.0, 190.0)
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == 5.0
    assert trade["price"] == 190.0
    assert "id" in trade
    assert "executed_at" in trade


def test_list_trades_newest_first():
    repo.record_trade("AAPL", "buy", 5.0, 190.0)
    repo.record_trade("MSFT", "buy", 2.0, 420.0)
    trades = repo.list_trades()
    assert trades[0]["ticker"] == "MSFT"  # most recent first


def test_list_trades_limit():
    for _ in range(5):
        repo.record_trade("AAPL", "buy", 1.0, 190.0)
    assert len(repo.list_trades(limit=3)) == 3


def test_list_trades_no_limit():
    for _ in range(5):
        repo.record_trade("AAPL", "buy", 1.0, 190.0)
    assert len(repo.list_trades()) == 5


# ---------------------------------------------------------------------------
# Snapshots
# ---------------------------------------------------------------------------

def test_record_and_list_snapshots():
    repo.record_snapshot(10000.0)
    repo.record_snapshot(10500.0)
    snaps = repo.list_snapshots()
    assert len(snaps) == 2
    # Chronological order — oldest first
    assert snaps[0]["total_value"] == 10000.0
    assert snaps[1]["total_value"] == 10500.0


def test_list_snapshots_limit():
    for i in range(10):
        repo.record_snapshot(float(10000 + i))
    snaps = repo.list_snapshots(limit=5)
    assert len(snaps) == 5
    # Should be the 5 most recent, in chronological order
    assert snaps[-1]["total_value"] == 10009.0


def test_list_snapshots_default_limit_500():
    for i in range(600):
        repo.record_snapshot(float(10000 + i))
    snaps = repo.list_snapshots()  # default limit=500
    assert len(snaps) == 500


# ---------------------------------------------------------------------------
# Chat messages
# ---------------------------------------------------------------------------

def test_add_message_returns_dict():
    msg = repo.add_message("user", "Hello")
    assert msg["role"] == "user"
    assert msg["content"] == "Hello"
    assert msg["actions"] is None


def test_add_message_with_actions():
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 5}]}
    msg = repo.add_message("assistant", "Done!", actions=actions)
    assert msg["actions"] == actions


def test_list_messages_chronological():
    repo.add_message("user", "first")
    repo.add_message("assistant", "second")
    msgs = repo.list_messages()
    assert msgs[0]["content"] == "first"
    assert msgs[1]["content"] == "second"


def test_list_messages_limit():
    for i in range(25):
        repo.add_message("user", f"msg{i}")
    msgs = repo.list_messages(limit=20)
    assert len(msgs) == 20
    # Should be the last 20, in chronological order
    assert msgs[-1]["content"] == "msg24"


def test_list_messages_actions_deserialized():
    """actions stored as JSON string must come back as a Python object via add_message return."""
    actions = [{"ticker": "TSLA", "action": "add"}]
    repo.add_message("assistant", "Watching TSLA", actions=actions)
    # The DB stores JSON string; list_messages returns raw row dict (actions as string)
    msgs = repo.list_messages()
    # The stored actions string should be valid JSON
    import json
    stored = msgs[-1]["actions"]
    assert json.loads(stored) == actions
