"""Persist the user's ticker list between sessions.

Kept separate from confluence/config.py: config.py is source-controlled
defaults, this file is per-user runtime state (gitignored).
"""

from __future__ import annotations

import json
from pathlib import Path

from confluence.config import DEFAULT_TICKERS

STATE_FILE = Path(__file__).resolve().parent.parent.parent / "tickers.local.json"


def load_tickers() -> list[str]:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return list(DEFAULT_TICKERS)
        if isinstance(data, list) and data and all(isinstance(x, str) for x in data):
            return data
    return list(DEFAULT_TICKERS)


def save_tickers(tickers: list[str]) -> None:
    STATE_FILE.write_text(json.dumps(tickers, indent=2))
