"""Attach indicator columns (RSI, SMAs, swing points) to raw OHLCV data."""

from __future__ import annotations

import pandas as pd

from confluence.config import RSI_PERIOD, SMA_PERIODS, SWING_ORDER
from confluence.indicators.swings import find_swings
from confluence.indicators.ta import rsi, sma


def enrich(
    df: pd.DataFrame,
    *,
    rsi_period: int = RSI_PERIOD,
    sma_periods: tuple[int, ...] = SMA_PERIODS,
    swing_order: int = SWING_ORDER,
) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi(out["close"], rsi_period)
    for period in sma_periods:
        out[f"sma{period}"] = sma(out["close"], period)
    out = find_swings(out, order=swing_order)
    return out
