"""Tests for deterministic mock LLM responses."""
from app.llm.mock import get_mock_response


def test_plain_message():
    r = get_mock_response("How is my portfolio doing?")
    assert r.message
    assert r.trades == []
    assert r.watchlist_changes == []


def test_buy_intent():
    r = get_mock_response("Please buy some AAPL")
    assert len(r.trades) == 1
    assert r.trades[0].side == "buy"
    assert r.trades[0].ticker == "AAPL"
    assert r.trades[0].quantity == 1
    assert r.watchlist_changes == []


def test_sell_intent():
    r = get_mock_response("sell my AAPL shares")
    assert len(r.trades) == 1
    assert r.trades[0].side == "sell"
    assert r.trades[0].ticker == "AAPL"
    assert r.watchlist_changes == []


def test_add_intent():
    r = get_mock_response("add TSLA to my watchlist")
    assert r.trades == []
    assert len(r.watchlist_changes) == 1
    assert r.watchlist_changes[0].action == "add"
    assert r.watchlist_changes[0].ticker == "TSLA"


def test_remove_intent():
    r = get_mock_response("remove TSLA from watchlist")
    assert r.trades == []
    assert len(r.watchlist_changes) == 1
    assert r.watchlist_changes[0].action == "remove"
    assert r.watchlist_changes[0].ticker == "TSLA"


def test_buy_takes_priority_over_add():
    """'buy' is checked before 'add' so a message with both triggers buy."""
    r = get_mock_response("buy and add something")
    assert len(r.trades) == 1
    assert r.trades[0].side == "buy"
