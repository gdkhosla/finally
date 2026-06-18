"""FastAPI application: lifespan wiring, API routes, static SPA serving."""
import asyncio
import pathlib
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import SNAPSHOT_INTERVAL_SECONDS, STATIC_DIR
from app.db import init_db, repo
from app.market import create_stream_router
from app.services.portfolio import get_portfolio
from app.state import market_source, price_cache


async def _snapshot_loop() -> None:
    """Record a portfolio value snapshot every SNAPSHOT_INTERVAL_SECONDS."""
    while True:
        await asyncio.sleep(SNAPSHOT_INTERVAL_SECONDS)
        repo.record_snapshot(get_portfolio()["total_value"])


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    tickers = repo.list_watchlist()
    await market_source.start(tickers)
    snapshot_task = asyncio.create_task(_snapshot_loop())
    yield
    snapshot_task.cancel()
    await market_source.stop()


app = FastAPI(title="FinAlly", lifespan=lifespan)

app.include_router(create_stream_router(price_cache))

from app.api import health, portfolio, watchlist  # noqa: E402

app.include_router(health.router)
app.include_router(portfolio.router)
app.include_router(watchlist.router)

try:
    from app.api import chat  # noqa: E402

    app.include_router(chat.router)
except ImportError:
    pass


# Static SPA serving. Skipped in local dev when the export does not exist.
_static_path = pathlib.Path(STATIC_DIR)
if _static_path.is_dir():
    app.mount(
        "/_next",
        StaticFiles(directory=_static_path / "_next"),
        name="next-assets",
    )

    @app.get("/{full_path:path}")
    async def spa_fallback(full_path: str):
        candidate = _static_path / full_path
        if full_path and candidate.is_file():
            return FileResponse(candidate)
        return FileResponse(_static_path / "index.html")
