"""RealDataProvider: DataProvider backed by Binance's public REST API
(confluence/data/binance_client.py). No API key required — Binance's
market-data endpoints (klines, ticker price) are public.

Translates this app's internal timeframe labels ("1D", "4H", "1H",
"15min") to Binance's interval codes via confluence.config.TIMEFRAMES;
everything else is a direct pass-through to binance_client.
"""

from __future__ import annotations

import pandas as pd

from confluence.config import CANDLE_LIMIT, TIMEFRAMES
from confluence.data.binance_client import BinanceAPIError, fetch_current_price, fetch_klines
from confluence.data.providers.base import DataProvider, DataProviderError


class RealDataProvider(DataProvider):
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
        if timeframe not in TIMEFRAMES:
            raise DataProviderError(f"unsupported timeframe '{timeframe}'")
        try:
            return fetch_klines(symbol, TIMEFRAMES[timeframe], limit=limit)
        except BinanceAPIError as exc:
            raise DataProviderError(str(exc)) from exc

    def get_current_price(self, symbol: str) -> float:
        try:
            return fetch_current_price(symbol)
        except BinanceAPIError as exc:
            raise DataProviderError(str(exc)) from exc
