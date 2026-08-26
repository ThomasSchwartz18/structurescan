"""Market-data source abstraction.

Every consumer in this app (indicators, screening, the API layer) talks
only to this interface, never to a concrete provider. MockDataProvider
implements it today with synthetic data. A future RealDataProvider (e.g.
wrapping Binance's public REST API, see confluence/data/binance_client.py)
implements the same interface and can be swapped in wherever a
DataProvider is constructed, with no changes to any calling code.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd

from confluence.config import CANDLE_LIMIT


class DataProviderError(RuntimeError):
    """Raised when a provider can't return data for a symbol/timeframe."""


class DataProvider(ABC):
    @abstractmethod
    def get_ohlcv(self, symbol: str, timeframe: str, limit: int = CANDLE_LIMIT) -> pd.DataFrame:
        """Return `limit` closed candles for symbol/timeframe, oldest first.

        `timeframe` is one of this app's internal labels ("1D", "4H",
        "1H", "15min" — see confluence.config.TIMEFRAMES), not a
        provider-specific code; translating to whatever the backing
        service needs is the provider's job.

        Returned columns: open_time, open, high, low, close, volume,
        close_time (open_time/close_time are UTC-aware pandas Timestamps).
        This is the same shape confluence.indicators.enrich.enrich()
        expects, and the same shape confluence.data.binance_client
        already returns.
        """

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """Return the latest traded price for symbol."""
