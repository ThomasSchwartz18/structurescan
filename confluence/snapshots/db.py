"""SQLite schema + connection helper for criteria snapshots.

A snapshot is a frozen point-in-time capture of a ticker's full screened
state — so a later question like "what did Confluence say about XRPUSDT
around 10:22am" can be answered from history instead of memory.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

DB_FILE = Path(__file__).resolve().parent.parent.parent / "snapshots.local.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS criteria_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    captured_at TEXT NOT NULL,
    payload TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_snapshots_symbol_time
    ON criteria_snapshots (symbol, captured_at);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path if db_path is not None else DB_FILE
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
