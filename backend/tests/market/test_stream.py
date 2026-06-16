"""
Tests for the SSE stream router.
"""
import asyncio
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.market.cache import PriceCache
from app.market.stream import create_stream_router, _price_generator, SSE_RETRY_MS


# ── _price_generator unit tests ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_price_generator_emits_retry_first():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    request = MagicMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    events = []
    async for chunk in _price_generator(request, cache):
        events.append(chunk)
        if len(events) >= 2:
            break

    assert events[0] == f"retry: {SSE_RETRY_MS}\n\n"


@pytest.mark.asyncio
async def test_price_generator_emits_price_data():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    # Disconnect after first data event
    request = MagicMock()
    request.is_disconnected = AsyncMock(side_effect=[False, True])

    events = []
    async for chunk in _price_generator(request, cache):
        events.append(chunk)
        if len(events) >= 2:
            break

    # Should have retry + data
    assert len(events) == 2
    data_event = events[1]
    assert data_event.startswith("data: ")
    payload = json.loads(data_event.replace("data: ", "").strip())
    assert "AAPL" in payload
    assert payload["AAPL"]["price"] == 190.0


@pytest.mark.asyncio
async def test_price_generator_stops_on_disconnect():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    # Disconnect immediately after first check
    request = MagicMock()
    request.is_disconnected = AsyncMock(return_value=True)

    events = []
    async for chunk in _price_generator(request, cache):
        events.append(chunk)
        if len(events) > 5:
            break  # safety

    # Only the retry directive should be emitted before disconnect
    assert events == [f"retry: {SSE_RETRY_MS}\n\n"]


@pytest.mark.asyncio
async def test_price_generator_emits_on_version_change():
    cache = PriceCache()
    cache.update("AAPL", 190.0)

    # Two polls: first sees version change, second disconnects
    call_count = 0
    async def is_disconnected():
        nonlocal call_count
        call_count += 1
        return call_count > 2  # disconnect on 3rd call

    request = MagicMock()
    request.is_disconnected = is_disconnected

    events = []
    async for chunk in _price_generator(request, cache):
        events.append(chunk)
        if call_count > 2:
            break

    # retry + at least one data event
    assert any("data:" in e for e in events)


# ── create_stream_router ──────────────────────────────────────────────────────


def test_create_stream_router_returns_api_router():
    from fastapi import APIRouter
    cache = PriceCache()
    router = create_stream_router(cache)
    assert isinstance(router, APIRouter)


def test_stream_router_has_prices_route():
    cache = PriceCache()
    router = create_stream_router(cache)
    routes = [r.path for r in router.routes]
    assert "/api/stream/prices" in routes
