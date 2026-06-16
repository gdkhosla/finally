# Starting prices (authoritative; PLAN.md values are illustrative only)
SEED_PRICES: dict[str, float] = {
    "AAPL":  190.00,
    "GOOGL": 175.00,
    "MSFT":  420.00,
    "AMZN":  185.00,
    "TSLA":  250.00,
    "NVDA":  870.00,
    "META":  510.00,
    "JPM":   200.00,
    "V":     275.00,
    "NFLX":  625.00,
}

# Per-ticker GBM parameters: annualized drift (mu) and volatility (sigma)
TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"mu": 0.05, "sigma": 0.22},
    "GOOGL": {"mu": 0.06, "sigma": 0.24},
    "MSFT":  {"mu": 0.07, "sigma": 0.20},
    "AMZN":  {"mu": 0.08, "sigma": 0.28},
    "TSLA":  {"mu": 0.03, "sigma": 0.50},  # high vol, low drift
    "NVDA":  {"mu": 0.10, "sigma": 0.40},  # high vol, high drift
    "META":  {"mu": 0.06, "sigma": 0.26},
    "JPM":   {"mu": 0.05, "sigma": 0.17},
    "V":     {"mu": 0.06, "sigma": 0.18},
    "NFLX":  {"mu": 0.04, "sigma": 0.30},
}

# Params for unknown tickers added dynamically via watchlist / trade auto-add
DEFAULT_PARAMS: dict[str, float] = {"mu": 0.05, "sigma": 0.25}

# Sector membership for correlation matrix
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech":    {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
    # TSLA is intentionally absent — treated as its own uncorrelated name
}

# Pairwise correlation coefficients
INTRA_TECH_CORR: float    = 0.6
INTRA_FINANCE_CORR: float = 0.5
CROSS_GROUP_CORR: float   = 0.3
TSLA_CORR: float          = 0.3  # TSLA vs everything
