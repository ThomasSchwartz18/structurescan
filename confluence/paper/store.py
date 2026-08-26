"""Paper trading business logic: open/close trades, journal queries, stats.

P&L is never stored as a running account balance that could drift out of
sync — it's always derived: realized P&L is computed once at close time
from (entry, exit, size, direction) and stored on that trade row: equity
is starting_balance + sum(realized P&L of closed trades). Unrealized P&L
for open trades is computed fresh from whatever price the DataProvider
returns, every time it's asked for.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

DIRECTIONS = ("long", "short")


class PaperTradingError(ValueError):
    """Raised for invalid trade parameters or invalid state transitions."""


@dataclass
class Trade:
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

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "Trade":
        return cls(**{key: row[key] for key in row.keys()})


@dataclass
class Stats:
    starting_balance: float
    realized_pnl_total: float
    equity: float
    closed_count: int
    win_count: int
    loss_count: int
    win_rate: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def compute_pnl(trade: Trade, price: float) -> float:
    if trade.direction == "long":
        return (price - trade.entry_price) * trade.size
    return (trade.entry_price - price) * trade.size


def open_trade(
    conn: sqlite3.Connection,
    *,
    symbol: str,
    direction: str,
    entry_price: float,
    size: float,
    stop_loss: Optional[float],
    take_profit: Optional[float],
    reasoning: str,
) -> Trade:
    symbol = symbol.strip().upper()
    if not symbol:
        raise PaperTradingError("symbol is required")
    if direction not in DIRECTIONS:
        raise PaperTradingError(f"direction must be one of {DIRECTIONS}")
    if entry_price <= 0:
        raise PaperTradingError("entry_price must be positive")
    if size <= 0:
        raise PaperTradingError("size must be positive")
    if not reasoning or not reasoning.strip():
        raise PaperTradingError("reasoning is required")

    cursor = conn.execute(
        """
        INSERT INTO trades
            (symbol, direction, entry_price, size, stop_loss, take_profit, reasoning, opened_at, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open')
        """,
        (symbol, direction, entry_price, size, stop_loss, take_profit, reasoning.strip(), _now_iso()),
    )
    conn.commit()
    return get_trade(conn, cursor.lastrowid)


def get_trade(conn: sqlite3.Connection, trade_id: int) -> Trade:
    row = conn.execute("SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        raise PaperTradingError(f"no trade with id {trade_id}")
    return Trade.from_row(row)


def list_open_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute("SELECT * FROM trades WHERE status = 'open' ORDER BY opened_at DESC").fetchall()
    return [Trade.from_row(row) for row in rows]


def list_closed_trades(conn: sqlite3.Connection) -> list[Trade]:
    rows = conn.execute("SELECT * FROM trades WHERE status = 'closed' ORDER BY closed_at DESC").fetchall()
    return [Trade.from_row(row) for row in rows]


def close_trade(conn: sqlite3.Connection, trade_id: int, exit_price: float) -> Trade:
    trade = get_trade(conn, trade_id)
    if trade.status != "open":
        raise PaperTradingError(f"trade {trade_id} is already closed")
    if exit_price <= 0:
        raise PaperTradingError("exit_price must be positive")

    pnl = compute_pnl(trade, exit_price)
    conn.execute(
        "UPDATE trades SET status = 'closed', exit_price = ?, closed_at = ?, realized_pnl = ? WHERE id = ?",
        (exit_price, _now_iso(), pnl, trade_id),
    )
    conn.commit()
    return get_trade(conn, trade_id)


def get_starting_balance(conn: sqlite3.Connection) -> float:
    row = conn.execute("SELECT starting_balance FROM account WHERE id = 1").fetchone()
    return row["starting_balance"]


def compute_stats(conn: sqlite3.Connection) -> Stats:
    starting_balance = get_starting_balance(conn)
    closed = list_closed_trades(conn)
    pnls = [trade.realized_pnl for trade in closed]
    total = sum(pnls) if pnls else 0.0
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    return Stats(
        starting_balance=starting_balance,
        realized_pnl_total=total,
        equity=starting_balance + total,
        closed_count=len(closed),
        win_count=len(wins),
        loss_count=len(losses),
        win_rate=(len(wins) / len(closed)) if closed else None,
        avg_win=(sum(wins) / len(wins)) if wins else None,
        avg_loss=(sum(losses) / len(losses)) if losses else None,
    )
