import math
import pytest
import numpy as np

from app.market.simulator import GBMSimulator, SimulatorDataSource, DEFAULT_DT
from app.market.cache import PriceCache
from app.market.seed_prices import SEED_PRICES


# ── GBMSimulator tests ────────────────────────────────────────────────────────


def test_initial_prices_match_seed():
    sim = GBMSimulator(["AAPL", "MSFT"])
    assert sim.get_price("AAPL") == SEED_PRICES["AAPL"]
    assert sim.get_price("MSFT") == SEED_PRICES["MSFT"]


def test_get_tickers_returns_all():
    sim = GBMSimulator(["AAPL", "MSFT", "TSLA"])
    tickers = sim.get_tickers()
    assert set(tickers) == {"AAPL", "MSFT", "TSLA"}


def test_step_returns_all_tickers():
    sim = GBMSimulator(["AAPL", "MSFT"])
    result = sim.step()
    assert set(result.keys()) == {"AAPL", "MSFT"}


def test_prices_always_positive():
    sim = GBMSimulator(["AAPL", "MSFT", "TSLA", "NVDA"], event_probability=0)
    for _ in range(500):
        prices = sim.step()
    assert all(p > 0 for p in prices.values())


def test_prices_positive_with_events():
    sim = GBMSimulator(["AAPL", "TSLA"], event_probability=1.0)  # always event
    for _ in range(200):
        prices = sim.step()
    assert all(p > 0 for p in prices.values())


def test_step_empty_tickers_returns_empty():
    sim = GBMSimulator([])
    result = sim.step()
    assert result == {}


def test_add_ticker_appears_in_step():
    sim = GBMSimulator(["AAPL"])
    sim.add_ticker("TSLA")
    assert "TSLA" in sim.get_tickers()
    prices = sim.step()
    assert "TSLA" in prices


def test_add_existing_ticker_is_noop():
    sim = GBMSimulator(["AAPL"])
    price_before = sim.get_price("AAPL")
    sim.add_ticker("AAPL")
    # Price should not have changed and it shouldn't appear twice
    assert sim.get_tickers().count("AAPL") == 1
    assert sim.get_price("AAPL") == price_before


def test_remove_ticker_disappears_from_step():
    sim = GBMSimulator(["AAPL", "TSLA"])
    sim.remove_ticker("TSLA")
    assert "TSLA" not in sim.get_tickers()
    prices = sim.step()
    assert "TSLA" not in prices


def test_remove_nonexistent_ticker_noop():
    sim = GBMSimulator(["AAPL"])
    sim.remove_ticker("DOESNOTEXIST")  # should not raise
    prices = sim.step()
    assert "AAPL" in prices


def test_add_remove_rebuilds_cholesky():
    sim = GBMSimulator(["AAPL"])
    sim.add_ticker("TSLA")
    prices = sim.step()  # should not raise
    assert "TSLA" in prices
    sim.remove_ticker("TSLA")
    prices = sim.step()
    assert "TSLA" not in prices
    assert "AAPL" in prices


def test_unknown_ticker_gets_default_seed():
    sim = GBMSimulator(["XYZUNKNOWN"])
    price = sim.get_price("XYZUNKNOWN")
    assert price is not None
    assert 0.01 <= price <= 1000.0  # random in [50, 300], floored at 0.01


def test_correlated_tickers_positive_covariance():
    """AAPL and MSFT (both tech) should show positive correlation over many steps."""
    sim = GBMSimulator(["AAPL", "MSFT"], event_probability=0)
    aapl_returns, msft_returns = [], []
    prev = {"AAPL": sim.get_price("AAPL"), "MSFT": sim.get_price("MSFT")}
    for _ in range(2000):
        prices = sim.step()
        aapl_returns.append((prices["AAPL"] - prev["AAPL"]) / prev["AAPL"])
        msft_returns.append((prices["MSFT"] - prev["MSFT"]) / prev["MSFT"])
        prev = dict(prices)
    cov = sum(a * b for a, b in zip(aapl_returns, msft_returns)) / len(aapl_returns)
    assert cov > 0, "Expect positive covariance for correlated sector tickers"


def test_tsla_correlation_is_independent():
    """TSLA (rho=0.3 vs everything) should co-move less tightly with AAPL than
    a same-sector tech pair (rho=0.6).

    This must compare the *Pearson correlation coefficient*, not raw covariance:
    covariance of returns is rho * sigma_a * sigma_b, so TSLA's much higher
    volatility (sigma=0.50) would dominate a raw-covariance comparison even though
    its correlation is lower. Normalizing by the standard deviations isolates rho.
    """
    sim_corr = GBMSimulator(["AAPL", "MSFT"], event_probability=0)
    sim_tsla = GBMSimulator(["AAPL", "TSLA"], event_probability=0)

    def get_correlation(sim, a, b, steps=4000):
        a_rets, b_rets = [], []
        prev = {a: sim.get_price(a), b: sim.get_price(b)}
        for _ in range(steps):
            prices = sim.step()
            a_rets.append((prices[a] - prev[a]) / prev[a])
            b_rets.append((prices[b] - prev[b]) / prev[b])
            prev = dict(prices)
        mean_a = sum(a_rets) / len(a_rets)
        mean_b = sum(b_rets) / len(b_rets)
        cov = sum((x - mean_a) * (y - mean_b) for x, y in zip(a_rets, b_rets))
        var_a = sum((x - mean_a) ** 2 for x in a_rets)
        var_b = sum((y - mean_b) ** 2 for y in b_rets)
        return cov / math.sqrt(var_a * var_b)

    corr_tech = get_correlation(sim_corr, "AAPL", "MSFT")
    corr_tsla = get_correlation(sim_tsla, "AAPL", "TSLA")
    assert corr_tech > corr_tsla, (
        "Same-sector tech correlation (rho=0.6) should exceed the TSLA pair (rho=0.3)"
    )


def test_price_floor_at_one_cent():
    """With dt=1.0 and huge negative sigma we can't force price to 0, but floor must hold."""
    # Use very small dt with normal settings, no way to go below 0.01 floor
    sim = GBMSimulator(["AAPL"], dt=DEFAULT_DT, event_probability=0)
    # Artificially crash the price
    sim._prices["AAPL"] = 0.001
    prices = sim.step()
    assert prices["AAPL"] >= 0.01


def test_correlation_tech_tech():
    sim = GBMSimulator(["AAPL", "GOOGL"])
    rho = sim._correlation("AAPL", "GOOGL")
    assert rho == 0.6


def test_correlation_finance_finance():
    sim = GBMSimulator(["JPM", "V"])
    rho = sim._correlation("JPM", "V")
    assert rho == 0.5


def test_correlation_cross_group():
    sim = GBMSimulator(["AAPL", "JPM"])
    rho = sim._correlation("AAPL", "JPM")
    assert rho == 0.3


def test_correlation_tsla():
    sim = GBMSimulator(["AAPL", "TSLA"])
    rho = sim._correlation("AAPL", "TSLA")
    assert rho == 0.3
    rho2 = sim._correlation("TSLA", "AAPL")
    assert rho2 == 0.3


def test_cholesky_valid_after_add():
    """Cholesky matrix should be valid (no NaN/inf) after adding a ticker."""
    sim = GBMSimulator(["AAPL", "MSFT"])
    sim.add_ticker("TSLA")
    chol = sim._chol
    assert chol is not None
    assert not np.any(np.isnan(chol))
    assert not np.any(np.isinf(chol))


# ── SimulatorDataSource tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_simulator_data_source_seeds_cache():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL", "GOOGL"])
    try:
        assert cache.get_price("AAPL") is not None
        assert cache.get_price("GOOGL") is not None
    finally:
        await src.stop()


@pytest.mark.asyncio
async def test_simulator_data_source_get_tickers():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL", "MSFT"])
    try:
        assert set(src.get_tickers()) == {"AAPL", "MSFT"}
    finally:
        await src.stop()


@pytest.mark.asyncio
async def test_simulator_data_source_add_ticker():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL"])
    try:
        await src.add_ticker("TSLA")
        assert "TSLA" in src.get_tickers()
        assert cache.get_price("TSLA") is not None
    finally:
        await src.stop()


@pytest.mark.asyncio
async def test_simulator_data_source_remove_ticker():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL", "MSFT"])
    try:
        await src.remove_ticker("MSFT")
        assert "MSFT" not in src.get_tickers()
        assert cache.get_price("MSFT") is None
    finally:
        await src.stop()


@pytest.mark.asyncio
async def test_simulator_data_source_stop_is_idempotent():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=60.0)
    await src.start(["AAPL"])
    await src.stop()
    await src.stop()  # second stop should not raise


@pytest.mark.asyncio
async def test_simulator_data_source_get_tickers_before_start():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache)
    assert src.get_tickers() == []


@pytest.mark.asyncio
async def test_simulator_data_source_add_ticker_before_start_noop():
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache)
    await src.add_ticker("AAPL")  # should not raise
    assert src.get_tickers() == []


@pytest.mark.asyncio
async def test_simulator_data_source_updates_cache_on_tick():
    """After a tick, cache version should have increased."""
    import asyncio
    cache = PriceCache()
    src = SimulatorDataSource(price_cache=cache, update_interval=0.05)
    await src.start(["AAPL"])
    try:
        v0 = cache.version
        await asyncio.sleep(0.2)  # allow at least one tick
        assert cache.version > v0
    finally:
        await src.stop()
