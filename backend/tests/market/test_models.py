import pytest
from app.market.models import PriceUpdate


def test_price_update_direction_up():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1000.0)
    assert u.direction == "up"


def test_price_update_direction_down():
    u = PriceUpdate(ticker="AAPL", price=189.0, previous_price=190.0, timestamp=1000.0)
    assert u.direction == "down"


def test_price_update_direction_flat():
    u = PriceUpdate(ticker="AAPL", price=190.0, previous_price=190.0, timestamp=1000.0)
    assert u.direction == "flat"


def test_price_update_change():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1000.0)
    assert u.change == 1.0


def test_price_update_change_negative():
    u = PriceUpdate(ticker="AAPL", price=189.0, previous_price=190.0, timestamp=1000.0)
    assert u.change == -1.0


def test_price_update_change_percent():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1000.0)
    expected = round(1.0 / 190.0 * 100, 4)
    assert u.change_percent == pytest.approx(expected)


def test_price_update_change_percent_zero_previous():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=0.0, timestamp=1000.0)
    assert u.change_percent == 0.0


def test_price_update_to_dict_keys():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1000.0)
    d = u.to_dict()
    assert set(d.keys()) == {"ticker", "price", "previous_price", "timestamp", "change", "change_percent", "direction"}


def test_price_update_to_dict_values():
    u = PriceUpdate(ticker="MSFT", price=420.0, previous_price=419.5, timestamp=9999.0)
    d = u.to_dict()
    assert d["ticker"] == "MSFT"
    assert d["price"] == 420.0
    assert d["previous_price"] == 419.5
    assert d["timestamp"] == 9999.0
    assert d["direction"] == "up"


def test_price_update_is_frozen():
    u = PriceUpdate(ticker="AAPL", price=191.0, previous_price=190.0, timestamp=1000.0)
    with pytest.raises(Exception):
        u.price = 200.0  # type: ignore[misc]
