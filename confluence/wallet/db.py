"""SQLite schema + connection helper for the wallet-scan trade journal.

Kept in its own file/table, separate from the paper trading journal
(confluence/paper/): these are real trades read from wallet history, not
simulated ones against a virtual account — conflating the two would make
"win rate" and "total P&L" ambiguous about whether real or practice money
is being measured.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent.parent / "wallet_journal.local.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS wallet_trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token_symbol TEXT NOT NULL,
    direction TEXT NOT NULL,
    entry_price REAL NOT NULL,
    entry_timestamp TEXT NOT NULL,
    entry_tx_hash TEXT NOT NULL UNIQUE,
    exit_price REAL,
    exit_timestamp TEXT,
    exit_tx_hash TEXT,
    size REAL NOT NULL,
    realized_pnl REAL,
    gas_fee_total REAL NOT NULL,
    position_status TEXT NOT NULL CHECK (position_status IN ('open', 'closed')),
    review_status TEXT NOT NULL CHECK (review_status IN ('needs_review', 'logged')) DEFAULT 'needs_review',
    reasoning TEXT,
    linked_snapshot_id INTEGER,
    criteria_met_count INTEGER,
    criteria_total_count INTEGER,
    annotated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_wallet_trades_review_status ON wallet_trades (review_status);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else DB_FILE
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
