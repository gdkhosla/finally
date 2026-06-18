"""Tests for the LLM structured output schema."""
import pytest
from pydantic import ValidationError

from app.llm.schema import LLMResponse, TradeAction, WatchlistChange


def test_llm_response_defaults():
    r = LLMResponse(message="hello")
    assert r.message == "hello"
    assert r.trades == []
    assert r.watchlist_changes == []


def test_llm_response_full():
    r = LLMResponse(
        message="Buying AAPL",
        trades=[TradeAction(ticker="AAPL", side="buy", quantity=5.0)],
        watchlist_changes=[WatchlistChange(ticker="TSLA", action="add")],
    )
    assert len(r.trades) == 1
    assert r.trades[0].ticker == "AAPL"
    assert r.trades[0].side == "buy"
    assert r.trades[0].quantity == 5.0
    assert len(r.watchlist_changes) == 1
    assert r.watchlist_changes[0].ticker == "TSLA"
    assert r.watchlist_changes[0].action == "add"


def test_llm_response_missing_message():
    with pytest.raises(ValidationError):
        LLMResponse()


def test_llm_response_from_dict():
    """Structured output parsing from a dict (simulates SDK parse result)."""
    data = {
        "message": "Here is my analysis.",
        "trades": [{"ticker": "MSFT", "side": "sell", "quantity": 2.5}],
        "watchlist_changes": [],
    }
    r = LLMResponse(**data)
    assert r.trades[0].ticker == "MSFT"
