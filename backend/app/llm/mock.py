"""Deterministic mock LLM responses for testing (LLM_MOCK=true).

Keying rules (substring match on lowercased message text, checked in order):
  - contains "buy"   -> trades=[{ticker:"AAPL", side:"buy", quantity:1}]
  - contains "sell"  -> trades=[{ticker:"AAPL", side:"sell", quantity:1}]
  - contains "add"   -> watchlist_changes=[{ticker:"TSLA", action:"add"}]
  - contains "remove"-> watchlist_changes=[{ticker:"TSLA", action:"remove"}]
  - otherwise        -> no trades or watchlist_changes (plain message)
"""
from app.llm.schema import LLMResponse, TradeAction, WatchlistChange


def get_mock_response(message: str) -> LLMResponse:
    """Return a deterministic LLMResponse based on message content."""
    text = message.lower()

    if "buy" in text:
        return LLMResponse(
            message="Mock: buying 1 share of AAPL for you.",
            trades=[TradeAction(ticker="AAPL", side="buy", quantity=1)],
        )
    if "sell" in text:
        return LLMResponse(
            message="Mock: selling 1 share of AAPL for you.",
            trades=[TradeAction(ticker="AAPL", side="sell", quantity=1)],
        )
    if "add" in text:
        return LLMResponse(
            message="Mock: adding TSLA to your watchlist.",
            watchlist_changes=[WatchlistChange(ticker="TSLA", action="add")],
        )
    if "remove" in text:
        return LLMResponse(
            message="Mock: removing TSLA from your watchlist.",
            watchlist_changes=[WatchlistChange(ticker="TSLA", action="remove")],
        )
    return LLMResponse(message="Mock: I can help you analyze your portfolio and execute trades.")
