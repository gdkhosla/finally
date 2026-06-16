import asyncio
import logging
import math
import random
import numpy as np
from time import time

from .cache import PriceCache
from .interface import MarketDataSource
from .seed_prices import (
    SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
    CORRELATION_GROUPS, INTRA_TECH_CORR, INTRA_FINANCE_CORR,
    CROSS_GROUP_CORR, TSLA_CORR,
)

logger = logging.getLogger(__name__)

# 252 trading days × 6.5 hours × 3600 seconds = one trading year in seconds
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600
DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR  # 500 ms as a year-fraction
DEFAULT_EVENT_PROBABILITY = 0.001             # 0.1% per tick per ticker


class GBMSimulator:
    """
    Pure price engine. Synchronous and stateless w.r.t. asyncio.
    Unit-testable without any async machinery.
    """

    def __init__(
        self,
        tickers: list[str],
        dt: float = DEFAULT_DT,
        event_probability: float = DEFAULT_EVENT_PROBABILITY,
    ) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._tickers: list[str] = []
        self._chol: np.ndarray | None = None  # Cholesky factor, rebuilt on membership change

        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers one tick. Returns {ticker: new_price}."""
        n = len(self._tickers)
        if n == 0:
            return {}

        # Draw correlated normals via Cholesky decomposition
        z = np.random.standard_normal(n)
        z_corr = self._chol @ z  # shape (n,)

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            p = self._prices[ticker]
            mu = self._params[ticker]["mu"]
            sigma = self._params[ticker]["sigma"]
            dt = self._dt

            # GBM discrete step: S(t+dt) = S(t) * exp((mu - σ²/2)*dt + σ*√dt*Z)
            drift = (mu - 0.5 * sigma ** 2) * dt
            diffusion = sigma * math.sqrt(dt) * z_corr[i]
            new_price = p * math.exp(drift + diffusion)

            # Random event shock: ±2–5% spike, 0.1% probability
            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                new_price *= (1 + shock)

            new_price = max(round(new_price, 2), 0.01)  # floor at 1 cent
            self._prices[ticker] = new_price
            result[ticker] = new_price

        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        params = TICKER_PARAMS.get(ticker, DEFAULT_PARAMS)
        seed = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._tickers.append(ticker)
        self._prices[ticker] = round(seed, 2)
        self._params[ticker] = params

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n == 0:
            self._chol = np.zeros((0, 0))
            return

        # Build correlation matrix
        C = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._correlation(self._tickers[i], self._tickers[j])
                C[i, j] = rho
                C[j, i] = rho

        # Cholesky decomposition; add small jitter if not positive-definite
        try:
            L = np.linalg.cholesky(C)
        except np.linalg.LinAlgError:
            C += np.eye(n) * 1e-6
            L = np.linalg.cholesky(C)
        self._chol = L

    def _correlation(self, a: str, b: str) -> float:
        if a == "TSLA" or b == "TSLA":
            return TSLA_CORR
        for group, members in CORRELATION_GROUPS.items():
            if a in members and b in members:
                if group == "tech":
                    return INTRA_TECH_CORR
                if group == "finance":
                    return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR


class SimulatorDataSource(MarketDataSource):
    """Wraps GBMSimulator, drives the background tick loop, writes to PriceCache."""

    def __init__(
        self,
        price_cache: PriceCache,
        update_interval: float = 0.5,
        dt: float = DEFAULT_DT,
        event_probability: float = DEFAULT_EVENT_PROBABILITY,
    ) -> None:
        self._cache = price_cache
        self._interval = update_interval
        self._dt = dt
        self._event_prob = event_probability
        self._engine: GBMSimulator | None = None
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        self._engine = GBMSimulator(tickers, dt=self._dt, event_probability=self._event_prob)
        # Seed the cache immediately so the first SSE connection has data
        for ticker, price in self._engine._prices.items():
            self._cache.update(ticker, price)
        self._task = asyncio.create_task(self._run_loop(), name="simulator-loop")

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def add_ticker(self, ticker: str) -> None:
        if self._engine is None:
            return
        self._engine.add_ticker(ticker)
        price = self._engine.get_price(ticker)
        if price is not None:
            self._cache.update(ticker, price)

    async def remove_ticker(self, ticker: str) -> None:
        if self._engine is None:
            return
        self._engine.remove_ticker(ticker)
        self._cache.remove(ticker)

    def get_tickers(self) -> list[str]:
        return self._engine.get_tickers() if self._engine else []

    async def _run_loop(self) -> None:
        while True:
            try:
                await asyncio.sleep(self._interval)
                if self._engine is None:
                    continue
                prices = self._engine.step()
                ts = time()
                for ticker, price in prices.items():
                    self._cache.update(ticker, price, timestamp=ts)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Simulator tick error — continuing")
