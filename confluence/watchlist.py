"""Persist the user's ticker watchlist between sessions.

Shared by every frontend (Tkinter UI, web API) — there's one watchlist,
not one per surface. Kept separate from confluence/config.py: config.py
holds source-controlled defaults, this file is per-user runtime state
(gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

from confluence.config import DEFAULT_TICKERS

STATE_FILE = Path(__file__).resolve().parent.parent / "tickers.local.json"


def load_tickers() -> list[str]:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return list(DEFAULT_TICKERS)
        # A saved *empty* list is valid (the user removed every ticker) and
        # must be honored, not silently overridden by the defaults below.
        if isinstance(data, list) and all(isinstance(x, str) for x in data):
            return data
    return list(DEFAULT_TICKERS)


def save_tickers(tickers: list[str]) -> None:
    STATE_FILE.write_text(json.dumps(tickers, indent=2))
