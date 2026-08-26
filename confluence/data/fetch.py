"""Fetch + enrich OHLCV data across timeframes and tickers."""

from __future__ import annotations

import pandas as pd

from confluence.config import CANDLE_LIMIT, TIMEFRAMES
from confluence.data.binance_client import fetch_klines
from confluence.indicators.enrich import enrich


def fetch_ticker(
    symbol: str,
    timeframes: dict[str, str] = TIMEFRAMES,
    limit: int = CANDLE_LIMIT,
) -> dict[str, pd.DataFrame]:
    """Fetch and enrich every configured timeframe for one symbol.

    Returns {timeframe_label: enriched DataFrame}. Raises BinanceAPIError
    (propagated from fetch_klines) if any timeframe fails to fetch — a
    partial/inconsistent set of timeframes for a ticker is worse than a
    clear failure for that ticker.
    """
    return {
        label: enrich(fetch_klines(symbol, interval, limit=limit))
        for label, interval in timeframes.items()
    }


def fetch_universe(
    symbols: list[str],
    timeframes: dict[str, str] = TIMEFRAMES,
    limit: int = CANDLE_LIMIT,
) -> dict[str, dict[str, pd.DataFrame] | Exception]:
    """Fetch every symbol in `symbols`.

    A failure for one symbol (e.g. an unlisted pair, a transient network
    error) is captured as the dict value rather than aborting the whole
    batch, so one bad ticker doesn't take down the screen for the rest.
    """
    results: dict[str, dict[str, pd.DataFrame] | Exception] = {}
    for symbol in symbols:
        try:
            results[symbol] = fetch_ticker(symbol, timeframes=timeframes, limit=limit)
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            results[symbol] = exc
    return results
