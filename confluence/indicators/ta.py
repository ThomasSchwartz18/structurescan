"""Technical indicator calculations.

RSI uses Wilder's original smoothing method (SMA-seeded recursive average),
which is what TradingView's built-in RSI uses. A plain rolling-mean RSI
will NOT match TradingView values.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def _wilder_smooth(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing, seeded per his original method.

    `series` is expected to be a gain/loss series derived from `.diff()`,
    whose first element is always NaN (no prior candle to diff against).
    The first `period` real values therefore live at positions 1..period,
    so the seed (a plain average) lands at index `period`, not `period - 1`.
    """
    values = series.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)

    if len(values) <= period:
        return pd.Series(out, index=series.index)

    out[period] = values[1 : period + 1].mean()
    for i in range(period + 1, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period

    return pd.Series(out, index=series.index)


def _wilder_smooth_plain(series: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothing for a series with no leading NaN (e.g. True Range,
    which is well-defined from the first bar — unlike a `.diff()`-derived
    series). The seed (a plain average of the first `period` values) lands
    at index `period - 1`, not `period` as in `_wilder_smooth`.
    """
    values = series.to_numpy(dtype=float)
    out = np.full(values.shape, np.nan)

    if len(values) < period:
        return pd.Series(out, index=series.index)

    out[period - 1] = values[:period].mean()
    for i in range(period, len(values)):
        out[i] = (out[i - 1] * (period - 1) + values[i]) / period

    return pd.Series(out, index=series.index)


def true_range(df: pd.DataFrame) -> pd.Series:
    """True Range per bar: max of (high-low), |high-prev_close|,
    |low-prev_close|. The first bar has no prior close, so those two
    terms are NaN there and `max(..., skipna=True)` naturally reduces to
    just high-low — no special-casing needed."""
    prev_close = df["close"].shift(1)
    candidates = pd.concat(
        [
            df["high"] - df["low"],
            (df["high"] - prev_close).abs(),
            (df["low"] - prev_close).abs(),
        ],
        axis=1,
    )
    return candidates.max(axis=1)


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Average True Range, Wilder-smoothed (the standard/original method)."""
    return _wilder_smooth_plain(true_range(df), period)


def rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = _wilder_smooth(gain, period)
    avg_loss = _wilder_smooth(loss, period)

    rs = avg_gain / avg_loss
    result = 100 - (100 / (1 + rs))

    # avg_loss == 0 (all up moves in the window) -> RSI is 100, not NaN/inf.
    result = result.where(avg_loss != 0, 100.0)
    # avg_gain == 0 and avg_loss == 0 (no movement at all) -> undefined, leave NaN.
    result = result.where(~((avg_gain == 0) & (avg_loss == 0)), np.nan)

    return result
