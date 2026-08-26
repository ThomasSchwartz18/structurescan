"""SQLite schema + connection helper for the paper trading journal.

No real funds or exchange connection — this only ever records what the
user says they did, against prices the DataProvider returns.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from confluence.config import PAPER_STARTING_BALANCE

DB_FILE = Path(__file__).resolve().parent.parent.parent / "paper_trades.local.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS account (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    starting_balance REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    direction TEXT NOT NULL CHECK (direction IN ('long', 'short')),
    entry_price REAL NOT NULL CHECK (entry_price > 0),
    size REAL NOT NULL CHECK (size > 0),
    stop_loss REAL,
    take_profit REAL,
    reasoning TEXT NOT NULL,
    opened_at TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')) DEFAULT 'open',
    exit_price REAL,
    closed_at TEXT,
    realized_pnl REAL
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    """Open a connection, creating the schema and the single account row
    on first use. Idempotent and cheap enough to call per-request — this
    is a local single-user SQLite file, not a shared server."""
    path = db_path if db_path is not None else DB_FILE
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.execute(
        "INSERT OR IGNORE INTO account (id, starting_balance) VALUES (1, ?)",
        (PAPER_STARTING_BALANCE,),
    )
    conn.commit()
    return conn
