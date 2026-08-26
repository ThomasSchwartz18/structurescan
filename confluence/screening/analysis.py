"""Turn enriched OHLCV data into descriptive technical state.

Everything in this module reports facts about indicator/price state —
"MAs stacked bullish", "RSI 72.3 (overbought)", "higher-highs/higher-lows".
Nothing here is a buy/sell signal, and no function should ever be extended
to emit one. "Aligned"/"conflict" describes whether timeframes agree with
each other, not whether to act. Same for the extended criteria below
(20-MA distance, ATR extension, volume confirmation, RSI divergence,
risk/reward ratio, swing freshness): each reports an observed condition,
not an instruction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from confluence.config import (
    MA20_EXTENDED_THRESHOLD_PCT,
    RSI_OVERBOUGHT,
    RSI_OVERSOLD,
    SMA_PERIODS,
)
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

    # --- extended criteria (defaulted: optional/derived, and so existing
    # call sites that construct a TimeframeState for a single scenario
    # under test don't need to specify every one of these) ---
    ma20_distance_pct: Optional[float] = None  # signed % distance of close from its own 20-MA
    ma20_state: str = "insufficient_data"  # "extended" | "normal" | "insufficient_data"
    atr: Optional[float] = None
    extension_ratio: Optional[float] = None  # (close - nearest swing low) / ATR, in ATR units
    volume_ratio: Optional[float] = None  # last candle's volume / trailing average volume
    volume_state: str = "insufficient_data"  # "confirmed" | "weak" | "insufficient_data"
    rsi_divergence: str = "none"  # "none" | "bullish" | "bearish"
    candles_since_swing_high: Optional[int] = None
    candles_since_swing_low: Optional[int] = None


@dataclass
class TickerReport:
    symbol: str
    timeframes: dict[str, TimeframeState]
    alignment: str  # "aligned_bullish" | "aligned_bearish" | "conflict"
    rr_ratio: Optional[float] = None  # daily-timeframe distance-to-resistance / distance-to-support


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


def classify_ma20_distance(
    close: float, ma20: Optional[float], threshold_pct: float = MA20_EXTENDED_THRESHOLD_PCT
) -> tuple[Optional[float], str]:
    if ma20 is None or ma20 == 0:
        return None, "insufficient_data"
    distance_pct = (close - ma20) / ma20 * 100
    return distance_pct, ("extended" if abs(distance_pct) > threshold_pct else "normal")


def classify_volume(last_volume: float, avg_volume: Optional[float]) -> tuple[Optional[float], str]:
    if avg_volume is None or avg_volume == 0 or pd.isna(avg_volume):
        return None, "insufficient_data"
    ratio = last_volume / avg_volume
    return ratio, ("confirmed" if ratio >= 1.0 else "weak")


def compute_extension_ratio(
    close: float, swing_low: Optional[SwingRef], atr_value: Optional[float]
) -> Optional[float]:
    if swing_low is None or atr_value is None or atr_value == 0 or pd.isna(atr_value):
        return None
    return (close - swing_low.price) / atr_value


def detect_rsi_divergence(df_enriched: pd.DataFrame) -> str:
    """Compare the last two confirmed swing lows (bullish case) and the
    last two confirmed swing highs (bearish case) against RSI at those
    same candles. If both directions trigger at once (rare, contradictory
    evidence), report "none" rather than pick one arbitrarily."""
    lows = df_enriched.loc[df_enriched["swing_low"], ["low", "rsi"]]
    highs = df_enriched.loc[df_enriched["swing_high"], ["high", "rsi"]]

    bullish = False
    if len(lows) >= 2:
        prev_price, prev_rsi = lows["low"].iloc[-2], lows["rsi"].iloc[-2]
        last_price, last_rsi = lows["low"].iloc[-1], lows["rsi"].iloc[-1]
        if pd.notna(prev_rsi) and pd.notna(last_rsi) and last_price < prev_price and last_rsi > prev_rsi:
            bullish = True

    bearish = False
    if len(highs) >= 2:
        prev_price, prev_rsi = highs["high"].iloc[-2], highs["rsi"].iloc[-2]
        last_price, last_rsi = highs["high"].iloc[-1], highs["rsi"].iloc[-1]
        if pd.notna(prev_rsi) and pd.notna(last_rsi) and last_price > prev_price and last_rsi < prev_rsi:
            bearish = True

    if bullish and not bearish:
        return "bullish"
    if bearish and not bullish:
        return "bearish"
    return "none"


def candles_since_swing(df_enriched: pd.DataFrame, kind: str) -> Optional[int]:
    """Candles elapsed since the most recent confirmed swing high/low.
    Uses positional (not label) indexing so it's correct regardless of
    what the DataFrame's own index looks like."""
    flagged = np.flatnonzero(df_enriched[f"swing_{kind}"].to_numpy())
    if len(flagged) == 0:
        return None
    return int(len(df_enriched) - 1 - flagged[-1])


def compute_rr_ratio(
    current_price: float, nearest_swing_high: Optional[SwingRef], nearest_swing_low: Optional[SwingRef]
) -> Optional[float]:
    if nearest_swing_high is None or nearest_swing_low is None:
        return None
    distance_to_resistance = abs(nearest_swing_high.price - current_price)
    distance_to_support = abs(current_price - nearest_swing_low.price)
    if distance_to_support == 0:
        return None
    return distance_to_resistance / distance_to_support


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
    close = float(last["close"])

    ma_values: dict[int, Optional[float]] = {
        period: (float(last[f"sma{period}"]) if pd.notna(last[f"sma{period}"]) else None)
        for period in sma_periods
    }
    rsi_value = float(last["rsi"]) if pd.notna(last["rsi"]) else None
    nearest = nearest_swings(df_enriched)
    nearest_swing_high = SwingRef(**nearest["swing_high"]) if nearest["swing_high"] else None
    nearest_swing_low = SwingRef(**nearest["swing_low"]) if nearest["swing_low"] else None

    ma_stack = classify_ma_stack(ma_values)
    structure = classify_structure(df_enriched)

    atr_value = float(last["atr"]) if pd.notna(last.get("atr")) else None
    ma20_distance_pct, ma20_state = classify_ma20_distance(close, ma_values.get(20))
    volume_ratio, volume_state = classify_volume(
        float(last["volume"]), float(last["avg_volume"]) if pd.notna(last.get("avg_volume")) else None
    )

    return TimeframeState(
        timeframe=timeframe_label,
        last_close=close,
        rsi=rsi_value,
        rsi_zone=classify_rsi_zone(rsi_value),
        ma_values=ma_values,
        ma_stack=ma_stack,
        price_vs_ma={p: _price_vs_ma(close, ma_values[p]) for p in sma_periods},
        structure=structure,
        nearest_swing_high=nearest_swing_high,
        nearest_swing_low=nearest_swing_low,
        bias_state=_bias_state(ma_stack, structure),
        ma20_distance_pct=ma20_distance_pct,
        ma20_state=ma20_state,
        atr=atr_value,
        extension_ratio=compute_extension_ratio(close, nearest_swing_low, atr_value),
        volume_ratio=volume_ratio,
        volume_state=volume_state,
        rsi_divergence=detect_rsi_divergence(df_enriched),
        candles_since_swing_high=candles_since_swing(df_enriched, "high"),
        candles_since_swing_low=candles_since_swing(df_enriched, "low"),
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
    daily = timeframe_states.get("1D")
    rr_ratio = (
        compute_rr_ratio(daily.last_close, daily.nearest_swing_high, daily.nearest_swing_low)
        if daily is not None
        else None
    )
    return TickerReport(
        symbol=symbol,
        timeframes=timeframe_states,
        alignment=determine_alignment(timeframe_states),
        rr_ratio=rr_ratio,
    )
