"""Fetch + enrich OHLCV data across timeframes and tickers.

Two families of functions here:

- `fetch_ticker`/`fetch_universe` are hardcoded to Binance
  (confluence.data.binance_client) and back the terminal dashboard and
  Tkinter UI.
- `fetch_ticker_from_provider`/`fetch_universe_from_provider` take a
  DataProvider (confluence.data.providers) and back the web API, so the
  same orchestration logic works against MockDataProvider today and a
  future RealDataProvider later with no changes here.
"""

from __future__ import annotations

import pandas as pd

from confluence.config import CANDLE_LIMIT, TIMEFRAMES
from confluence.data.binance_client import fetch_klines
from confluence.data.providers.base import DataProvider
from confluence.indicators.enrich import enrich

TIMEFRAME_LABELS = list(TIMEFRAMES.keys())


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


def fetch_ticker_from_provider(
    provider: DataProvider,
    symbol: str,
    timeframe_labels: list[str] = TIMEFRAME_LABELS,
    limit: int = CANDLE_LIMIT,
) -> dict[str, pd.DataFrame]:
    """Provider-backed equivalent of `fetch_ticker`. See module docstring."""
    return {label: enrich(provider.get_ohlcv(symbol, label, limit)) for label in timeframe_labels}


def fetch_universe_from_provider(
    provider: DataProvider,
    symbols: list[str],
    timeframe_labels: list[str] = TIMEFRAME_LABELS,
    limit: int = CANDLE_LIMIT,
) -> dict[str, dict[str, pd.DataFrame] | Exception]:
    """Provider-backed equivalent of `fetch_universe`. See module docstring."""
    results: dict[str, dict[str, pd.DataFrame] | Exception] = {}
    for symbol in symbols:
        try:
            results[symbol] = fetch_ticker_from_provider(
                provider, symbol, timeframe_labels=timeframe_labels, limit=limit
            )
        except Exception as exc:  # noqa: BLE001 - deliberately broad, see docstring
            results[symbol] = exc
    return results
