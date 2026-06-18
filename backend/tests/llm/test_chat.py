"""Tests for the chat route with mocked portfolio/watchlist services."""
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Stub 'massive' before any app imports
if "massive" not in sys.modules:
    sys.modules["massive"] = MagicMock()
    sys.modules["massive.rest"] = MagicMock()
    sys.modules["massive.rest.models"] = MagicMock()


@pytest.fixture(autouse=True)
def set_llm_mock_env(monkeypatch):
    """Always run chat tests in mock mode."""
    monkeypatch.setenv("LLM_MOCK", "true")


@pytest.fixture()
def mock_db(tmp_path, monkeypatch):
    """Point the DB at a temp file and initialize it."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("FINALLY_DB_PATH", db_path)

    # Re-initialize connection and schema for the temp DB
    from app.db.connection import get_conn
    from app.db.schema import init_db
    init_db()
    return db_path


@pytest.fixture()
def mock_services():
    """Patch portfolio.execute_trade and watchlist services so no real market source is needed."""
    with (
        patch(
            "app.services.portfolio.execute_trade",
            new_callable=AsyncMock,
            return_value={"ok": True, "trade": {"ticker": "AAPL", "side": "buy", "quantity": 1}, "fill_price": 150.0},
        ) as mock_trade,
        patch(
            "app.services.watchlist.add_ticker_to_watchlist",
            new_callable=AsyncMock,
            return_value={"ok": True, "ticker": "TSLA"},
        ) as mock_add,
        patch(
            "app.services.watchlist.remove_ticker_from_watchlist",
            new_callable=AsyncMock,
            return_value={"ok": True, "ticker": "TSLA"},
        ) as mock_remove,
    ):
        yield {"execute_trade": mock_trade, "add": mock_add, "remove": mock_remove}


@pytest.fixture()
def chat_endpoint(mock_db, mock_services):
    """Import and return the chat endpoint function."""
    import importlib
    import app.api.chat as chat_mod
    importlib.reload(chat_mod)
    return chat_mod.chat


class FakeRequest:
    def __init__(self, message: str):
        self.message = message


@pytest.mark.asyncio
async def test_plain_message(chat_endpoint):
    resp = await chat_endpoint(FakeRequest("How is my portfolio?"))
    assert "message" in resp
    assert resp["trades"] == []
    assert resp["watchlist_changes"] == []


@pytest.mark.asyncio
async def test_buy_trade_executed(chat_endpoint, mock_services):
    with patch("app.api.chat._execute_trades", new_callable=AsyncMock, return_value=[
        {"ticker": "AAPL", "side": "buy", "quantity": 1, "ok": True, "fill_price": 150.0}
    ]):
        resp = await chat_endpoint(FakeRequest("please buy AAPL"))
    assert len(resp["trades"]) == 1
    assert resp["trades"][0]["ticker"] == "AAPL"
    assert resp["trades"][0]["ok"] is True


@pytest.mark.asyncio
async def test_watchlist_add_executed(chat_endpoint):
    with patch("app.api.chat._apply_watchlist_changes", new_callable=AsyncMock, return_value=[
        {"ticker": "TSLA", "action": "add", "ok": True}
    ]):
        resp = await chat_endpoint(FakeRequest("add TSLA to my watchlist"))
    assert len(resp["watchlist_changes"]) == 1
    assert resp["watchlist_changes"][0]["action"] == "add"
    assert resp["watchlist_changes"][0]["ok"] is True


@pytest.mark.asyncio
async def test_messages_stored(mock_db, chat_endpoint):
    """User and assistant messages are stored in the DB."""
    from app.db import repo
    with (
        patch("app.api.chat._execute_trades", new_callable=AsyncMock, return_value=[]),
        patch("app.api.chat._apply_watchlist_changes", new_callable=AsyncMock, return_value=[]),
    ):
        await chat_endpoint(FakeRequest("Tell me about my portfolio"))
    messages = repo.list_messages(10)
    roles = [m["role"] for m in messages]
    assert "user" in roles
    assert "assistant" in roles
