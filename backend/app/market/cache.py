import threading
from time import time
from .models import PriceUpdate


class PriceCache:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._prices: dict[str, PriceUpdate] = {}
        self._version: int = 0

    @property
    def version(self) -> int:
        return self._version

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        ts = timestamp if timestamp is not None else time()
        price = round(price, 2)
        with self._lock:
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price  # first update → flat
            update = PriceUpdate(
                ticker=ticker,
                price=price,
                previous_price=previous_price,
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
        return update

    def get(self, ticker: str) -> PriceUpdate | None:
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        with self._lock:
            self._prices.pop(ticker, None)
            self._version += 1
