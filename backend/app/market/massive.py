import asyncio
import logging
from time import time

from .cache import PriceCache
from .interface import MarketDataSource

logger = logging.getLogger(__name__)

# Poll every 15 s on free tier (5 req/min). Paid tiers can reduce to 2-5 s.
DEFAULT_POLL_INTERVAL = 15.0


class MassiveDataSource(MarketDataSource):
    """
    Polls the Massive (Polygon.io) REST API for live prices.
    The SDK is synchronous; all blocking calls run in asyncio.to_thread().
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._tickers: set[str] = set()
        self._task: asyncio.Task | None = None
        self._client = None  # created lazily in start()

    async def start(self, tickers: list[str]) -> None:
        # Import here so tests without the massive package don't fail at import time
        from massive import RESTClient
        self._client = RESTClient(api_key=self._api_key)
        self._tickers = set(tickers)
        # Fetch once immediately so the cache is populated before returning
        await self._poll_once()
        self._task = asyncio.create_task(self._run_loop(), name="massive-poll-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def add_ticker(self, ticker: str) -> None:
        self._tickers.add(ticker)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers.discard(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                await self._poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Massive poll error — will retry next cycle")

    async def _poll_once(self) -> None:
        if not self._tickers:
            return
        tickers_list = list(self._tickers)
        snapshots = await asyncio.to_thread(self._fetch_snapshots, tickers_list)
        for snap in snapshots:
            try:
                price = snap.last_trade.price
                # SDK normalizes timestamp to milliseconds; convert to seconds
                ts_snap = snap.last_trade.timestamp / 1000.0
            except (AttributeError, TypeError):
                logger.debug("Skipping %s — missing last_trade data", getattr(snap, "ticker", "?"))
                continue
            self._cache.update(ticker=snap.ticker, price=price, timestamp=ts_snap)

    def _fetch_snapshots(self, tickers: list[str]):
        """Synchronous — runs in a worker thread via asyncio.to_thread."""
        from massive.rest.models import SnapshotMarketType
        try:
            return list(
                self._client.get_snapshot_all(
                    market_type=SnapshotMarketType.STOCKS,
                    tickers=tickers,
                )
            )
        except Exception:
            logger.exception("Massive get_snapshot_all failed")
            return []
