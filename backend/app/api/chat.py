"""Chat API — POST /api/chat."""
import os

from fastapi import APIRouter
from pydantic import BaseModel

from app.db import repo
from app.llm.mock import get_mock_response
from app.llm.schema import LLMResponse

router = APIRouter()

_LLM_MOCK = os.environ.get("LLM_MOCK", "false").lower() == "true"


class ChatRequest(BaseModel):
    message: str


async def _get_llm_response(message: str) -> LLMResponse:
    if _LLM_MOCK:
        return get_mock_response(message)
    from app.llm.client import generate_response
    return await generate_response(message)


async def _execute_trades(trades) -> list[dict]:
    from app.services.portfolio import execute_trade
    results = []
    for t in trades:
        result = await execute_trade(t.ticker, t.side, t.quantity)
        results.append({"ticker": t.ticker, "side": t.side, "quantity": t.quantity, **result})
    return results


async def _apply_watchlist_changes(changes) -> list[dict]:
    from app.services.watchlist import add_ticker_to_watchlist, remove_ticker_from_watchlist
    results = []
    for c in changes:
        if c.action == "add":
            result = await add_ticker_to_watchlist(c.ticker)
        else:
            result = await remove_ticker_from_watchlist(c.ticker)
        results.append({"ticker": c.ticker, "action": c.action, **result})
    return results


@router.post("/api/chat")
async def chat(request: ChatRequest):
    """Receive a user message, call the LLM, auto-execute actions, return the response."""
    repo.add_message("user", request.message)

    parsed = await _get_llm_response(request.message)

    trade_results = await _execute_trades(parsed.trades)
    watchlist_results = await _apply_watchlist_changes(parsed.watchlist_changes)

    repo.add_message(
        "assistant",
        parsed.message,
        actions={"trades": trade_results, "watchlist_changes": watchlist_results},
    )

    return {
        "message": parsed.message,
        "trades": trade_results,
        "watchlist_changes": watchlist_results,
    }
