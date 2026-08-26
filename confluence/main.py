"""Confluence entrypoint: refresh the terminal dashboard on a schedule.

Usage:
    python -m confluence.main [refresh_seconds]
"""

from __future__ import annotations

import sys
import time

from rich.console import Console
from rich.live import Live

from confluence.config import CANDLE_LIMIT, DEFAULT_TICKERS, TIMEFRAMES
from confluence.data.fetch import fetch_universe
from confluence.output.dashboard import build_table
from confluence.screening.analysis import TickerReport, build_ticker_report

DEFAULT_REFRESH_SECONDS = 60


def build_reports(
    symbols: list[str],
    timeframes: dict[str, str] = TIMEFRAMES,
    limit: int = CANDLE_LIMIT,
) -> dict[str, TickerReport | Exception]:
    raw = fetch_universe(symbols, timeframes=timeframes, limit=limit)
    reports: dict[str, TickerReport | Exception] = {}
    for symbol, data in raw.items():
        reports[symbol] = data if isinstance(data, Exception) else build_ticker_report(symbol, data)
    return reports


def run(symbols: list[str] = DEFAULT_TICKERS, refresh_seconds: int = DEFAULT_REFRESH_SECONDS) -> None:
    console = Console()
    with Live(console=console, refresh_per_second=1, screen=False) as live:
        while True:
            reports = build_reports(symbols)
            live.update(build_table(reports))
            time.sleep(refresh_seconds)


if __name__ == "__main__":
    refresh = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REFRESH_SECONDS
    run(refresh_seconds=refresh)
