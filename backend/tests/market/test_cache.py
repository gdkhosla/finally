import threading
import pytest
from app.market.cache import PriceCache


def test_version_starts_at_zero():
    cache = PriceCache()
    assert cache.version == 0


def test_update_bumps_version():
    cache = PriceCache()
    v0 = cache.version
    cache.update("AAPL", 190.0)
    assert cache.version == v0 + 1


def test_update_bumps_version_each_time():
    cache = PriceCache()
    for i in range(5):
        cache.update("AAPL", 190.0 + i)
    assert cache.version == 5


def test_first_update_flat_direction():
    cache = PriceCache()
    u = cache.update("AAPL", 190.0)
    assert u.direction == "flat"
    assert u.change == 0.0
    assert u.change_percent == 0.0


def test_second_update_shows_direction():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    u = cache.update("AAPL", 191.0)
    assert u.direction == "up"
    u2 = cache.update("AAPL", 189.0)
    assert u2.direction == "down"


def test_price_rounded_to_2dp():
    cache = PriceCache()
    u = cache.update("AAPL", 190.1234567)
    assert u.price == 190.12


def test_get_returns_latest():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("AAPL", 195.0)
    u = cache.get("AAPL")
    assert u is not None
    assert u.price == 195.0


def test_get_nonexistent_returns_none():
    cache = PriceCache()
    assert cache.get("UNKNOWN") is None


def test_get_price_returns_float():
    cache = PriceCache()
    cache.update("MSFT", 420.0)
    assert cache.get_price("MSFT") == 420.0


def test_get_price_nonexistent_returns_none():
    cache = PriceCache()
    assert cache.get_price("UNKNOWN") is None


def test_get_all_returns_all_tickers():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.update("MSFT", 420.0)
    all_prices = cache.get_all()
    assert "AAPL" in all_prices
    assert "MSFT" in all_prices


def test_get_all_returns_copy():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    all_prices = cache.get_all()
    all_prices["NEW"] = None  # type: ignore[assignment]
    assert "NEW" not in cache.get_all()


def test_remove_ticker():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    cache.remove("AAPL")
    assert cache.get("AAPL") is None


def test_remove_bumps_version():
    cache = PriceCache()
    cache.update("AAPL", 190.0)
    v = cache.version
    cache.remove("AAPL")
    assert cache.version == v + 1


def test_remove_nonexistent_does_not_raise():
    cache = PriceCache()
    cache.remove("DOESNOTEXIST")  # should not raise


def test_timestamp_used_when_provided():
    cache = PriceCache()
    u = cache.update("AAPL", 190.0, timestamp=12345.0)
    assert u.timestamp == 12345.0


def test_concurrent_updates_thread_safe():
    """Verify thread safety: many threads can update concurrently without error."""
    cache = PriceCache()
    errors = []

    def updater(ticker: str, price: float):
        try:
            for i in range(100):
                cache.update(ticker, price + i)
        except Exception as e:
            errors.append(e)

    threads = [
        threading.Thread(target=updater, args=(f"T{i}", 100.0 + i))
        for i in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Thread safety errors: {errors}"
    # All 10 tickers should be present
    all_prices = cache.get_all()
    for i in range(10):
        assert f"T{i}" in all_prices
