"""OpenAI gpt-5-nano client with structured outputs."""
import os

from openai import AsyncOpenAI

from app.db import repo
from app.llm.schema import LLMResponse

_client: AsyncOpenAI | None = None


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _client


def _build_system_prompt(portfolio: dict, watchlist: list[str]) -> str:
    positions_text = ""
    for p in portfolio.get("positions", []):
        positions_text += (
            f"  {p['ticker']}: {p['quantity']} shares @ avg ${p['avg_cost']:.2f}, "
            f"current ${p['current_price']:.2f}, P&L ${p['unrealized_pnl']:.2f} ({p['pct_change']:.1f}%)\n"
        )

    return f"""You are FinAlly, an AI trading assistant for a simulated portfolio.

Current portfolio:
  Cash: ${portfolio.get('cash_balance', 0):.2f}
  Total value: ${portfolio.get('total_value', 0):.2f}
  Unrealized P&L: ${portfolio.get('unrealized_pnl', 0):.2f}
  Positions:
{positions_text if positions_text else '  (none)'}
  Watchlist: {', '.join(watchlist) if watchlist else '(empty)'}

Instructions:
- Analyze portfolio composition, risk concentration, and P&L when relevant.
- Suggest trades with clear reasoning when asked.
- Execute trades when the user asks or agrees — include them in the trades array.
- Manage the watchlist proactively when appropriate.
- Be concise and data-driven. Use numbers from the portfolio context.
- Respond with valid structured JSON matching the required schema.
- This is a simulated environment with no real money at stake."""


async def generate_response(message: str) -> LLMResponse:
    """Call gpt-5-nano and return a parsed LLMResponse."""
    # Lazy import to avoid circular import if services aren't ready yet
    try:
        from app.services.portfolio import get_portfolio
        portfolio = get_portfolio()
    except Exception:
        portfolio = {"cash_balance": 0, "positions": [], "total_value": 0, "unrealized_pnl": 0}

    watchlist = repo.list_watchlist()
    history = repo.list_messages(20)

    system_prompt = _build_system_prompt(portfolio, watchlist)

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": message})

    client = _get_client()
    completion = await client.beta.chat.completions.parse(
        model="gpt-5-nano",
        messages=messages,
        response_format=LLMResponse,
    )
    return completion.choices[0].message.parsed
