"""Turn enriched OHLCV data into descriptive technical state.

Everything in this module reports facts about indicator/price state —
"MAs stacked bullish", "RSI 72.3 (overbought)", "higher-highs/higher-lows".
Nothing here is a buy/sell signal, and no function should ever be extended
to emit one. "Aligned"/"conflict" describes whether timeframes agree with
each other, not whether to act.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from confluence.config import RSI_OVERBOUGHT, RSI_OVERSOLD, SMA_PERIODS
from confluence.indicators.swings import nearest_swings, swing_sequence


@dataclass
class SwingRef:
    open_time: pd.Timestamp
    price: float


@dataclass
class TimeframeState:
    timeframe: str
    last_close: float
    rsi: Optional[float]
    rsi_zone: str  # "oversold" | "neutral" | "overbought" | "insufficient_data"
    ma_values: dict[int, Optional[float]]
    ma_stack: str  # "bullish" | "bearish" | "mixed" | "insufficient_data"
    price_vs_ma: dict[int, str]  # period -> "above" | "below" | "insufficient_data"
    structure: str  # "higher_highs_higher_lows" | "lower_highs_lower_lows" | "mixed" | "insufficient_data"
    nearest_swing_high: Optional[SwingRef]
    nearest_swing_low: Optional[SwingRef]
    bias_state: str  # "bullish_state" | "bearish_state" | "mixed_state" -- descriptive only


@dataclass
class TickerReport:
    symbol: str
    timeframes: dict[str, TimeframeState]
    alignment: str  # "aligned_bullish" | "aligned_bearish" | "conflict"


def classify_ma_stack(ma_values: dict[int, Optional[float]]) -> str:
    ordered = [ma_values[p] for p in sorted(ma_values)]
    if any(v is None for v in ordered):
        return "insufficient_data"
    if all(ordered[i] > ordered[i + 1] for i in range(len(ordered) - 1)):
        return "bullish"
    if all(ordered[i] < ordered[i + 1] for i in range(len(ordered) - 1)):
        return "bearish"
    return "mixed"


def classify_rsi_zone(value: Optional[float]) -> str:
    if value is None:
        return "insufficient_data"
    if value >= RSI_OVERBOUGHT:
        return "overbought"
    if value <= RSI_OVERSOLD:
        return "oversold"
    return "neutral"


def classify_structure(df_enriched: pd.DataFrame) -> str:
    highs = swing_sequence(df_enriched, "high")
    lows = swing_sequence(df_enriched, "low")
    if len(highs) < 2 or len(lows) < 2:
        return "insufficient_data"

    higher_high = highs["price"].iloc[-1] > highs["price"].iloc[-2]
    higher_low = lows["price"].iloc[-1] > lows["price"].iloc[-2]
    lower_high = highs["price"].iloc[-1] < highs["price"].iloc[-2]
    lower_low = lows["price"].iloc[-1] < lows["price"].iloc[-2]

    if higher_high and higher_low:
        return "higher_highs_higher_lows"
    if lower_high and lower_low:
        return "lower_highs_lower_lows"
    return "mixed"


def _price_vs_ma(close: float, ma_value: Optional[float]) -> str:
    if ma_value is None:
        return "insufficient_data"
    return "above" if close > ma_value else "below"


def _bias_state(ma_stack: str, structure: str) -> str:
    if ma_stack == "bullish" and structure == "higher_highs_higher_lows":
        return "bullish_state"
    if ma_stack == "bearish" and structure == "lower_highs_lower_lows":
        return "bearish_state"
    return "mixed_state"


def build_timeframe_state(
    timeframe_label: str,
    df_enriched: pd.DataFrame,
    sma_periods: tuple[int, ...] = SMA_PERIODS,
) -> TimeframeState:
    last = df_enriched.iloc[-1]

    ma_values: dict[int, Optional[float]] = {
        period: (float(last[f"sma{period}"]) if pd.notna(last[f"sma{period}"]) else None)
        for period in sma_periods
    }
    rsi_value = float(last["rsi"]) if pd.notna(last["rsi"]) else None
    nearest = nearest_swings(df_enriched)

    ma_stack = classify_ma_stack(ma_values)
    structure = classify_structure(df_enriched)

    return TimeframeState(
        timeframe=timeframe_label,
        last_close=float(last["close"]),
        rsi=rsi_value,
        rsi_zone=classify_rsi_zone(rsi_value),
        ma_values=ma_values,
        ma_stack=ma_stack,
        price_vs_ma={p: _price_vs_ma(float(last["close"]), ma_values[p]) for p in sma_periods},
        structure=structure,
        nearest_swing_high=SwingRef(**nearest["swing_high"]) if nearest["swing_high"] else None,
        nearest_swing_low=SwingRef(**nearest["swing_low"]) if nearest["swing_low"] else None,
        bias_state=_bias_state(ma_stack, structure),
    )


def determine_alignment(timeframe_states: dict[str, TimeframeState]) -> str:
    biases = {ts.bias_state for ts in timeframe_states.values()}
    if biases == {"bullish_state"}:
        return "aligned_bullish"
    if biases == {"bearish_state"}:
        return "aligned_bearish"
    return "conflict"


def build_ticker_report(symbol: str, enriched_by_timeframe: dict[str, pd.DataFrame]) -> TickerReport:
    timeframe_states = {
        label: build_timeframe_state(label, df) for label, df in enriched_by_timeframe.items()
    }
    return TickerReport(
        symbol=symbol,
        timeframes=timeframe_states,
        alignment=determine_alignment(timeframe_states),
    )
