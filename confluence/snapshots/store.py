"""Save/query criteria snapshots, and reconstruct a TickerReport back out
of one for downstream reuse (e.g. re-scoring it against the morning
report's criteria — see confluence/wallet/store.py).
"""

from __future__ import annotations

import dataclasses
import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

import pandas as pd

from confluence.config import SNAPSHOT_CAPTURE_INTERVAL_MINUTES, SNAPSHOT_RETENTION_DAYS
from confluence.screening.analysis import SwingRef, TickerReport, TimeframeState


@dataclass
class Snapshot:
    id: int
    symbol: str
    captured_at: str
    payload: dict


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_snapshot(row: sqlite3.Row) -> Snapshot:
    return Snapshot(id=row["id"], symbol=row["symbol"], captured_at=row["captured_at"], payload=json.loads(row["payload"]))


def save_snapshot(conn: sqlite3.Connection, report: TickerReport, captured_at: Optional[str] = None) -> Snapshot:
    captured_at = captured_at or _now_iso()
    # default=str handles the one non-JSON-native type in here (pandas
    # Timestamp inside SwingRef.open_time) by stringifying it; nothing in
    # this payload is ever read back into a typed object except via
    # reconstruct_report() below, which doesn't need open_time to be a
    # real Timestamp.
    payload = json.dumps(dataclasses.asdict(report), default=str)
    cursor = conn.execute(
        "INSERT INTO criteria_snapshots (symbol, captured_at, payload) VALUES (?, ?, ?)",
        (report.symbol, captured_at, payload),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM criteria_snapshots WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return _row_to_snapshot(row)


def prune_old_snapshots(conn: sqlite3.Connection, retention_days: int = SNAPSHOT_RETENTION_DAYS) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=retention_days)).isoformat()
    cursor = conn.execute("DELETE FROM criteria_snapshots WHERE captured_at < ?", (cutoff,))
    conn.commit()
    return cursor.rowcount


def latest_snapshot(conn: sqlite3.Connection, symbol: str) -> Optional[Snapshot]:
    row = conn.execute(
        "SELECT * FROM criteria_snapshots WHERE symbol = ? ORDER BY captured_at DESC LIMIT 1",
        (symbol.upper(),),
    ).fetchone()
    return _row_to_snapshot(row) if row else None


def maybe_save_snapshot(
    conn: sqlite3.Connection,
    report: TickerReport,
    interval_minutes: int = SNAPSHOT_CAPTURE_INTERVAL_MINUTES,
) -> Optional[Snapshot]:
    """Save a new snapshot only if the most recent one for this symbol is
    older than `interval_minutes` (or none exists yet). Returns the saved
    snapshot, or None if it was skipped. Opportunistically prunes old
    snapshots on every actual save, rather than needing a separate
    scheduled job for a local single-user SQLite file."""
    latest = latest_snapshot(conn, report.symbol)
    if latest is not None:
        elapsed = datetime.now(timezone.utc) - pd.Timestamp(latest.captured_at).to_pydatetime()
        if elapsed < timedelta(minutes=interval_minutes):
            return None
    snapshot = save_snapshot(conn, report)
    prune_old_snapshots(conn)
    return snapshot


def list_snapshots(conn: sqlite3.Connection, symbol: str, limit: int = 1000) -> list[Snapshot]:
    rows = conn.execute(
        "SELECT * FROM criteria_snapshots WHERE symbol = ? ORDER BY captured_at DESC LIMIT ?",
        (symbol.upper(), limit),
    ).fetchall()
    return [_row_to_snapshot(row) for row in rows]


def nearby_snapshots(conn: sqlite3.Connection, symbol: str, target_time: str, count: int = 5) -> list[Snapshot]:
    """The `count` snapshots for `symbol` closest in time to
    `target_time`, nearest first — for the annotation UI to let the user
    pick the right one rather than guessing from a full history list."""
    candidates = list_snapshots(conn, symbol)
    if not candidates:
        return []
    target = pd.Timestamp(target_time)
    candidates.sort(key=lambda s: abs(pd.Timestamp(s.captured_at) - target))
    return candidates[:count]


def get_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> Optional[Snapshot]:
    row = conn.execute("SELECT * FROM criteria_snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return _row_to_snapshot(row) if row else None


def reconstruct_report(snapshot: Snapshot) -> TickerReport:
    """Rebuild a TickerReport from a stored snapshot's payload, well
    enough to re-run confluence.screening.report.evaluate_criteria() on
    it. `SwingRef.open_time` ends up as the plain string it was stored
    as rather than a real pd.Timestamp — fine here, since none of the
    report criteria read that field, only `.price`."""
    data = snapshot.payload
    timeframes: dict[str, TimeframeState] = {}
    for label, tf in data["timeframes"].items():
        tf = dict(tf)
        tf["nearest_swing_high"] = SwingRef(**tf["nearest_swing_high"]) if tf["nearest_swing_high"] else None
        tf["nearest_swing_low"] = SwingRef(**tf["nearest_swing_low"]) if tf["nearest_swing_low"] else None
        tf["ma_values"] = {int(k): v for k, v in tf["ma_values"].items()}
        tf["price_vs_ma"] = {int(k): v for k, v in tf["price_vs_ma"].items()}
        timeframes[label] = TimeframeState(**tf)
    return TickerReport(
        symbol=data["symbol"],
        timeframes=timeframes,
        alignment=data["alignment"],
        rr_ratio=data["rr_ratio"],
    )
