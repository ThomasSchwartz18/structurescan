"""Wallet journal business logic: ingest normalized trade records,
manage the Needs Review -> Logged annotation flow, and compute stats
(including a breakdown by how many report criteria were met at entry).

`annotate_trade` takes an already-computed criteria_met_count/
criteria_total_count rather than looking a snapshot up and scoring it
itself — that orchestration (find the snapshot, run
confluence.screening.report.score_ticker on it) belongs to the API route
that has access to both the snapshots store and the report module; this
store stays a thin persistence layer, same as confluence/paper/store.py.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from confluence.wallet.normalize import WalletTradeRecord


class WalletJournalError(ValueError):
    pass


@dataclass
class WalletTrade:
    id: int
    token_symbol: str
    direction: str
    entry_price: float
    entry_timestamp: str
    entry_tx_hash: str
    exit_price: Optional[float]
    exit_timestamp: Optional[str]
    exit_tx_hash: Optional[str]
    size: float
    realized_pnl: Optional[float]
    gas_fee_total: float
    position_status: str
    review_status: str
    reasoning: Optional[str]
    linked_snapshot_id: Optional[int]
    criteria_met_count: Optional[int]
    criteria_total_count: Optional[int]
    annotated_at: Optional[str]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> "WalletTrade":
        return cls(**{key: row[key] for key in row.keys()})


@dataclass
class CriteriaBucketStats:
    met_count: int
    total_count: int
    trade_count: int
    win_count: int
    total_pnl: float
    win_rate: Optional[float]


@dataclass
class WalletStats:
    logged_count: int
    closed_count: int
    total_realized_pnl: float
    total_gas_fees: float
    win_count: int
    loss_count: int
    win_rate: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    by_criteria: list[CriteriaBucketStats]


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ingest_trade_records(conn: sqlite3.Connection, records: list[WalletTradeRecord]) -> int:
    """Insert new trade records, skipping any whose entry_tx_hash is
    already present — makes re-scanning the same wallet history
    idempotent instead of creating duplicates. Returns how many were
    actually inserted."""
    inserted = 0
    for record in records:
        exists = conn.execute(
            "SELECT 1 FROM wallet_trades WHERE entry_tx_hash = ?", (record.entry_tx_hash,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO wallet_trades
                (token_symbol, direction, entry_price, entry_timestamp, entry_tx_hash,
                 exit_price, exit_timestamp, exit_tx_hash, size, realized_pnl, gas_fee_total,
                 position_status, review_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'needs_review')
            """,
            (
                record.token_symbol,
                record.direction,
                record.entry_price,
                record.entry_timestamp,
                record.entry_tx_hash,
                record.exit_price,
                record.exit_timestamp,
                record.exit_tx_hash,
                record.size,
                record.realized_pnl,
                record.gas_fee_total,
                record.status,
            ),
        )
        inserted += 1
    conn.commit()
    return inserted


def get_wallet_trade(conn: sqlite3.Connection, trade_id: int) -> WalletTrade:
    row = conn.execute("SELECT * FROM wallet_trades WHERE id = ?", (trade_id,)).fetchone()
    if row is None:
        raise WalletJournalError(f"no wallet trade with id {trade_id}")
    return WalletTrade.from_row(row)


def list_needs_review(conn: sqlite3.Connection) -> list[WalletTrade]:
    rows = conn.execute(
        "SELECT * FROM wallet_trades WHERE review_status = 'needs_review' ORDER BY entry_timestamp DESC"
    ).fetchall()
    return [WalletTrade.from_row(row) for row in rows]


def list_logged(conn: sqlite3.Connection) -> list[WalletTrade]:
    rows = conn.execute(
        "SELECT * FROM wallet_trades WHERE review_status = 'logged' ORDER BY entry_timestamp DESC"
    ).fetchall()
    return [WalletTrade.from_row(row) for row in rows]


def annotate_trade(
    conn: sqlite3.Connection,
    trade_id: int,
    reasoning: str,
    *,
    linked_snapshot_id: Optional[int] = None,
    criteria_met_count: Optional[int] = None,
    criteria_total_count: Optional[int] = None,
) -> WalletTrade:
    if not reasoning or not reasoning.strip():
        raise WalletJournalError("reasoning is required")
    get_wallet_trade(conn, trade_id)  # raises if unknown

    conn.execute(
        """
        UPDATE wallet_trades
        SET reasoning = ?, linked_snapshot_id = ?, criteria_met_count = ?,
            criteria_total_count = ?, review_status = 'logged', annotated_at = ?
        WHERE id = ?
        """,
        (reasoning.strip(), linked_snapshot_id, criteria_met_count, criteria_total_count, _now_iso(), trade_id),
    )
    conn.commit()
    return get_wallet_trade(conn, trade_id)


def compute_wallet_stats(conn: sqlite3.Connection) -> WalletStats:
    logged = list_logged(conn)
    closed = [t for t in logged if t.position_status == "closed" and t.realized_pnl is not None]
    pnls = [t.realized_pnl for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]

    buckets: dict[int, list[WalletTrade]] = defaultdict(list)
    for trade in closed:
        if trade.criteria_met_count is not None:
            buckets[trade.criteria_met_count].append(trade)

    by_criteria = []
    for met_count in sorted(buckets, reverse=True):
        bucket = buckets[met_count]
        bucket_pnls = [t.realized_pnl for t in bucket]
        bucket_wins = [p for p in bucket_pnls if p > 0]
        by_criteria.append(
            CriteriaBucketStats(
                met_count=met_count,
                total_count=bucket[0].criteria_total_count,
                trade_count=len(bucket),
                win_count=len(bucket_wins),
                total_pnl=sum(bucket_pnls),
                win_rate=(len(bucket_wins) / len(bucket)) if bucket else None,
            )
        )

    return WalletStats(
        logged_count=len(logged),
        closed_count=len(closed),
        total_realized_pnl=sum(pnls) if pnls else 0.0,
        total_gas_fees=sum(t.gas_fee_total for t in logged),
        win_count=len(wins),
        loss_count=len(losses),
        win_rate=(len(wins) / len(closed)) if closed else None,
        avg_win=(sum(wins) / len(wins)) if wins else None,
        avg_loss=(sum(losses) / len(losses)) if losses else None,
        by_criteria=by_criteria,
    )
