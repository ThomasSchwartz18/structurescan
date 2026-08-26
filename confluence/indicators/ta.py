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
