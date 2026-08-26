"""Synthetic OHLCV data for UI development and demos.

Generates a deterministic (seeded) geometric random walk per
symbol/timeframe, anchored so the series' final close equals the
ticker's configured "current" price — every refresh call reproduces the
same numbers unless real wall-clock time has advanced into a new candle
period, which mimics how a live feed would behave without actually being
one.

Per-timeframe bias ("bullish"/"bearish"/"choppy") drives the average
drift per candle, so a ticker can be deliberately configured to show
clean trend alignment across all four timeframes, a clean opposing trend,
or a mix that produces the "conflict" alignment flag.
"""

from __future__ import annotations

import zlib

import numpy as np
import pandas as pd

from confluence.config import CANDLE_LIMIT
from confluence.data.providers.base import DataProvider, DataProviderError

PANDAS_FREQ = {
    "1D": "1D",
    "4H": "4h",
    "1H": "1h",
    "15min": "15min",
}

BIAS_PARAMS = {
    "bullish": {"drift": 0.0018, "vol": 0.0045},
    "bearish": {"drift": -0.0018, "vol": 0.0045},
    "choppy": {"drift": 0.0, "vol": 0.008},
}

# Curated demo tickers: two clean bullish alignments, one clean bearish
# alignment, two where timeframes deliberately disagree (-> "conflict").
#
# `seed_salt` pins the specific random draw used for a ticker. It only
# affects which noise pattern comes out of the same bias/volatility
# parameters above (not the trend direction itself) — it exists purely
# so these five demo tickers land on clean, illustrative examples of each
# alignment state instead of whatever a given seed happens to produce.
DEFAULT_SEED_SALT = "confluence-mock"

TICKER_PROFILES: dict[str, dict] = {
    "BTCUSDT": {
        "base_price": 65_000.0,
        "bias": {"1D": "bullish", "4H": "bullish", "1H": "bullish", "15min": "bullish"},
        "seed_salt": "confluence-mock-v0",
    },
    "XRPUSDT": {
        "base_price": 2.85,
        "bias": {"1D": "bullish", "4H": "bullish", "1H": "bullish", "15min": "bullish"},
        "seed_salt": "confluence-mock-v0",
    },
    "HYPEUSD": {
        "base_price": 26.40,
        "bias": {"1D": "bullish", "4H": "bullish", "1H": "bullish", "15min": "bullish"},
        "seed_salt": "confluence-mock-v0",
    },
    "SOLUSDT": {
        "base_price": 142.00,
        "bias": {"1D": "bearish", "4H": "bearish", "1H": "bearish", "15min": "bearish"},
        "seed_salt": "confluence-mock-v1",
    },
    "ADAUSDT": {
        "base_price": 0.74,
        "bias": {"1D": "bullish", "4H": "bearish", "1H": "bearish", "15min": "choppy"},
    },
    "DOGEUSDT": {
        "base_price": 0.185,
        "bias": {"1D": "choppy", "4H": "choppy", "1H": "bullish", "15min": "bearish"},
    },
}

DEFAULT_BIAS = {"1D": "choppy", "4H": "choppy", "1H": "choppy", "15min": "choppy"}


def _default_base_price(symbol: str) -> float:
    """Stable pseudo-price for a ticker with no curated profile, so
    ad-hoc "Add ticker" symbols still get plausible, consistent-looking
    data instead of every unknown symbol defaulting to the same price."""
    digest = zlib.crc32(symbol.encode())
    return round(0.1 + (digest % 100_000) / 1000, 4)


def _seed(symbol: str, timeframe: str, salt: str = DEFAULT_SEED_SALT) -> int:
    return zlib.crc32(f"{salt}:{symbol}:{timeframe}".encode()) & 0xFFFFFFFF


def profile_for(symbol: str) -> dict:
    profile = TICKER_PROFILES.get(symbol.upper())
    if profile is not None:
        return profile
    return {"base_price": _default_base_price(symbol.upper()), "bias": DEFAULT_BIAS}


def generate_ohlcv(
    symbol: str,
    timeframe: str,
    limit: int,
    *,
    bias: str,
    base_price: float,
    seed: int,
    now: pd.Timestamp,
) -> pd.DataFrame:
    """Pure candle generator (no wall-clock/randomness side effects beyond
    the given `seed`/`now`), kept separate from MockDataProvider so tests
    can call it with a fixed `now` for deterministic assertions."""
    if timeframe not in PANDAS_FREQ:
        raise DataProviderError(f"unsupported timeframe '{timeframe}'")
    if limit < 2:
        raise DataProviderError("limit must be >= 2")

    freq = PANDAS_FREQ[timeframe]
    offset = pd.tseries.frequencies.to_offset(freq)
    period_end = now.floor(freq)  # start of the still-forming candle -> excluded
    last_open_time = period_end - offset
    open_times = pd.date_range(end=last_open_time, periods=limit, freq=freq)
    close_times = open_times + offset - pd.Timedelta(milliseconds=1)

    params = BIAS_PARAMS[bias]
    rng = np.random.default_rng(seed)

    log_returns = rng.normal(params["drift"], params["vol"], limit)
    path = np.cumsum(log_returns)
    closes = base_price * np.exp(path - path[-1])  # anchor last close == base_price

    opens = np.empty(limit)
    opens[0] = closes[0] * float(np.exp(rng.normal(0, params["vol"] / 2)))
    opens[1:] = closes[:-1]

    wick = rng.uniform(0.001, 0.012, limit)
    highs = np.maximum(opens, closes) * (1 + wick)
    lows = np.minimum(opens, closes) * (1 - wick)
    volumes = rng.uniform(0.5, 1.5, limit) * base_price * 1000

    return pd.DataFrame(
        {
            "open_time": open_times,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "close_time": close_times,
        }
    )


class MockDataProvider(DataProvider):
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
        profile = profile_for(symbol)
        bias = profile["bias"].get(timeframe, "choppy")
        return generate_ohlcv(
            symbol,
            timeframe,
            limit,
            bias=bias,
            base_price=profile["base_price"],
            seed=_seed(symbol, timeframe, profile.get("seed_salt", DEFAULT_SEED_SALT)),
            now=pd.Timestamp.now(tz="UTC"),
        )

    def get_current_price(self, symbol: str) -> float:
        df = self.get_ohlcv(symbol, "15min", limit=2)
        return float(df["close"].iloc[-1])
