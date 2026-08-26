"""JSON response models + serializers for the web API.

Converts the plain dataclasses in confluence.screening.analysis into
Pydantic models. Field values are copied verbatim from those dataclasses
— this module adds no new screening logic, only a JSON-safe shape
(ISO timestamps, string-keyed dicts) for the same descriptive facts.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from confluence.screening.analysis import TickerReport, TimeframeState


class SwingRefOut(BaseModel):
    open_time: str
    price: float


class TimeframeStateOut(BaseModel):
    timeframe: str
    last_close: float
    rsi: Optional[float]
    rsi_zone: str
    ma_values: dict[str, Optional[float]]
    ma_stack: str
    price_vs_ma: dict[str, str]
    structure: str
    nearest_swing_high: Optional[SwingRefOut]
    nearest_swing_low: Optional[SwingRefOut]
    bias_state: str

    # extended criteria
    ma20_distance_pct: Optional[float]
    ma20_state: str
    atr: Optional[float]
    extension_ratio: Optional[float]
    volume_ratio: Optional[float]
    volume_state: str
    rsi_divergence: str
    candles_since_swing_high: Optional[int]
    candles_since_swing_low: Optional[int]


class TickerRowOut(BaseModel):
    symbol: str
    ok: bool
    error: Optional[str] = None
    current_price: Optional[float] = None
    alignment: Optional[str] = None
    rr_ratio: Optional[float] = None
    timeframes: Optional[dict[str, TimeframeStateOut]] = None


class BtcContextOut(BaseModel):
    symbol: str
    ma_stack: str  # "bullish" | "bearish" | "mixed" | "insufficient_data"


class WatchlistResponse(BaseModel):
    data_source: str
    generated_at: str
    btc_context: Optional[BtcContextOut] = None
    tickers: list[TickerRowOut]


def _swing_ref_out(ref) -> Optional[SwingRefOut]:
    if ref is None:
        return None
    return SwingRefOut(open_time=ref.open_time.isoformat(), price=ref.price)


def _timeframe_state_out(state: TimeframeState) -> TimeframeStateOut:
    return TimeframeStateOut(
        timeframe=state.timeframe,
        last_close=state.last_close,
        rsi=state.rsi,
        rsi_zone=state.rsi_zone,
        ma_values={str(period): value for period, value in state.ma_values.items()},
        ma_stack=state.ma_stack,
        price_vs_ma={str(period): value for period, value in state.price_vs_ma.items()},
        structure=state.structure,
        nearest_swing_high=_swing_ref_out(state.nearest_swing_high),
        nearest_swing_low=_swing_ref_out(state.nearest_swing_low),
        bias_state=state.bias_state,
        ma20_distance_pct=state.ma20_distance_pct,
        ma20_state=state.ma20_state,
        atr=state.atr,
        extension_ratio=state.extension_ratio,
        volume_ratio=state.volume_ratio,
        volume_state=state.volume_state,
        rsi_divergence=state.rsi_divergence,
        candles_since_swing_high=state.candles_since_swing_high,
        candles_since_swing_low=state.candles_since_swing_low,
    )


def to_ticker_row(
    symbol: str,
    *,
    report: Optional[TickerReport] = None,
    current_price: Optional[float] = None,
    error: Optional[str] = None,
) -> TickerRowOut:
    if error is not None:
        return TickerRowOut(symbol=symbol, ok=False, error=error)

    assert report is not None, "to_ticker_row requires either `report` or `error`"
    return TickerRowOut(
        symbol=symbol,
        ok=True,
        current_price=current_price,
        alignment=report.alignment,
        rr_ratio=report.rr_ratio,
        timeframes={label: _timeframe_state_out(state) for label, state in report.timeframes.items()},
    )
