"""Attach indicator columns (RSI, SMAs, ATR, volume average, swing points)
to raw OHLCV data."""

from __future__ import annotations

import pandas as pd

from confluence.config import ATR_PERIOD, RSI_PERIOD, SMA_PERIODS, SWING_ORDER, VOLUME_LOOKBACK
from confluence.indicators.swings import find_swings
from confluence.indicators.ta import atr, rsi, sma


def enrich(
    df: pd.DataFrame,
    *,
    rsi_period: int = RSI_PERIOD,
    sma_periods: tuple[int, ...] = SMA_PERIODS,
    swing_order: int = SWING_ORDER,
    atr_period: int = ATR_PERIOD,
    volume_lookback: int = VOLUME_LOOKBACK,
) -> pd.DataFrame:
    out = df.copy()
    out["rsi"] = rsi(out["close"], rsi_period)
    for period in sma_periods:
        out[f"sma{period}"] = sma(out["close"], period)
    out["atr"] = atr(out, atr_period)
    # Trailing average excludes the current candle itself, so "this candle's
    # volume vs. its own trailing average" isn't diluted by including itself.
    out["avg_volume"] = out["volume"].shift(1).rolling(window=volume_lookback, min_periods=volume_lookback).mean()
    out = find_swings(out, order=swing_order)
    return out
