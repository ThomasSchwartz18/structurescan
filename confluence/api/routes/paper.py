"""Paper trading endpoints: open/close virtual trades against whatever
price the shared DataProvider returns, and journal/stats queries over
what's already recorded. No real funds or exchange connection.
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from confluence.api.provider import provider
from confluence.paper.db import get_connection
from confluence.paper.store import (
    PaperTradingError,
    Stats,
    Trade,
    close_trade,
    compute_pnl,
    compute_stats,
    get_trade,
    list_closed_trades,
    list_open_trades,
    open_trade,
)

router = APIRouter(prefix="/paper", tags=["paper-trading"])


class OpenTradeRequest(BaseModel):
    symbol: str
    direction: Literal["long", "short"]
    entry_price: float
    size: float
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reasoning: str


class TradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    symbol: str
    direction: str
    entry_price: float
    size: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reasoning: str
    opened_at: str
    status: str
    exit_price: Optional[float]
    closed_at: Optional[str]
    realized_pnl: Optional[float]


class OpenTradeOut(TradeOut):
    current_price: Optional[float] = None
    unrealized_pnl: Optional[float] = None
    price_error: Optional[str] = None


class StatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    starting_balance: float
    realized_pnl_total: float
    equity: float
    closed_count: int
    win_count: int
    loss_count: int
    win_rate: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]


def _with_live_price(trade: Trade) -> OpenTradeOut:
    base = TradeOut.model_validate(trade).model_dump()
    try:
        price = provider.get_current_price(trade.symbol)
        return OpenTradeOut(**base, current_price=price, unrealized_pnl=compute_pnl(trade, price))
    except Exception as exc:  # noqa: BLE001 - isolate one bad symbol from the rest
        return OpenTradeOut(**base, price_error=str(exc))


@router.post("/trades", response_model=TradeOut)
def create_trade(payload: OpenTradeRequest) -> TradeOut:
    conn = get_connection()
    try:
        trade = open_trade(
            conn,
            symbol=payload.symbol,
            direction=payload.direction,
            entry_price=payload.entry_price,
            size=payload.size,
            stop_loss=payload.stop_loss,
            take_profit=payload.take_profit,
            reasoning=payload.reasoning,
        )
    except PaperTradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()
    return TradeOut.model_validate(trade)


@router.get("/trades/open", response_model=list[OpenTradeOut])
def get_open_trades() -> list[OpenTradeOut]:
    conn = get_connection()
    try:
        trades = list_open_trades(conn)
    finally:
        conn.close()
    return [_with_live_price(trade) for trade in trades]


@router.get("/trades/closed", response_model=list[TradeOut])
def get_closed_trades() -> list[TradeOut]:
    conn = get_connection()
    try:
        trades = list_closed_trades(conn)
    finally:
        conn.close()
    return [TradeOut.model_validate(trade) for trade in trades]


@router.post("/trades/{trade_id}/close", response_model=TradeOut)
def close_position(trade_id: int) -> TradeOut:
    conn = get_connection()
    try:
        trade = get_trade(conn, trade_id)
    except PaperTradingError as exc:
        conn.close()
        raise HTTPException(status_code=404, detail=str(exc))

    try:
        current_price = provider.get_current_price(trade.symbol)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
        conn.close()
        raise HTTPException(status_code=502, detail=f"could not fetch current price for {trade.symbol}: {exc}")

    try:
        closed = close_trade(conn, trade_id, current_price)
    except PaperTradingError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()
    return TradeOut.model_validate(closed)


@router.get("/stats", response_model=StatsOut)
def get_stats() -> Stats:
    conn = get_connection()
    try:
        return compute_stats(conn)
    finally:
        conn.close()
