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


class TickerRowOut(BaseModel):
    symbol: str
    ok: bool
    error: Optional[str] = None
    current_price: Optional[float] = None
    alignment: Optional[str] = None
    timeframes: Optional[dict[str, TimeframeStateOut]] = None


class WatchlistResponse(BaseModel):
    data_source: str
    generated_at: str
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
        timeframes={label: _timeframe_state_out(state) for label, state in report.timeframes.items()},
    )
