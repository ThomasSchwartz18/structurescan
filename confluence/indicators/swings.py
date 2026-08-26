"""Objective swing high/low detection.

A candle at index i is a confirmed swing high if its high is the maximum
within a symmetric window of `order` candles on each side (a standard
"fractal" definition). The same applies to swing lows using the minimum.
Because confirmation requires `order` candles *after* the point, the most
recent `order` candles can never be confirmed swings yet — that's correct,
not a bug: an unconfirmed high/low isn't an objective swing point.
"""

from __future__ import annotations

import pandas as pd


def find_swings(df: pd.DataFrame, order: int = 3) -> pd.DataFrame:
    """Return a copy of df with boolean 'swing_high' / 'swing_low' columns."""
    if order < 1:
        raise ValueError("order must be >= 1")

    out = df.copy()
    window = 2 * order + 1

    rolling_max = out["high"].rolling(window, center=True, min_periods=window).max()
    rolling_min = out["low"].rolling(window, center=True, min_periods=window).min()

    out["swing_high"] = out["high"].notna() & (out["high"] == rolling_max)
    out["swing_low"] = out["low"].notna() & (out["low"] == rolling_min)

    return out


def swing_sequence(df: pd.DataFrame, kind: str) -> pd.DataFrame:
    """Chronological list of confirmed swing points.

    `kind` is "high" or "low". Returns the subset of rows (open_time, price)
    where that swing type is flagged, oldest first.
    """
    if kind not in ("high", "low"):
        raise ValueError("kind must be 'high' or 'low'")

    col = f"swing_{kind}"
    price_col = "high" if kind == "high" else "low"
    points = df.loc[df[col], ["open_time", price_col]].rename(columns={price_col: "price"})
    return points.reset_index(drop=True)


def nearest_swings(df: pd.DataFrame) -> dict:
    """Most recent confirmed swing high and low as of the last candle.

    Returns {"swing_high": {...} | None, "swing_low": {...} | None}, each
    either None (no confirmed swing yet) or {"open_time", "price"}.
    """
    highs = swing_sequence(df, "high")
    lows = swing_sequence(df, "low")

    result = {"swing_high": None, "swing_low": None}
    if len(highs):
        last = highs.iloc[-1]
        result["swing_high"] = {"open_time": last["open_time"], "price": float(last["price"])}
    if len(lows):
        last = lows.iloc[-1]
        result["swing_low"] = {"open_time": last["open_time"], "price": float(last["price"])}
    return result
