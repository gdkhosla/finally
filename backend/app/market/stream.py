import asyncio
import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .cache import PriceCache

SSE_POLL_INTERVAL = 0.5   # seconds between cache version checks
SSE_RETRY_MS      = 1000  # tells EventSource to wait 1 s before reconnecting


def create_stream_router(price_cache: PriceCache) -> APIRouter:
    router = APIRouter()

    @router.get("/api/stream/prices")
    async def stream_prices(request: Request):
        return StreamingResponse(
            _price_generator(request, price_cache),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",  # disable nginx buffering if behind proxy
            },
        )

    return router


async def _price_generator(request: Request, cache: PriceCache):
    # Emit retry directive once so browser EventSource reconnects quickly
    yield f"retry: {SSE_RETRY_MS}\n\n"

    last_version = -1

    while True:
        # Check for client disconnect
        if await request.is_disconnected():
            break

        current_version = cache.version
        if current_version != last_version:
            last_version = current_version
            all_prices = cache.get_all()
            payload = {ticker: update.to_dict() for ticker, update in all_prices.items()}
            yield f"data: {json.dumps(payload)}\n\n"

        await asyncio.sleep(SSE_POLL_INTERVAL)
