from unittest.mock import patch

import pandas as pd
import pytest

from confluence.data.binance_client import BinanceAPIError
from confluence.data.providers.base import DataProviderError
from confluence.data.providers.real_provider import RealDataProvider


def _fake_klines_df():
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
            "open": [1.0, 1.1, 1.2],
            "high": [1.2, 1.3, 1.4],
            "low": [0.9, 1.0, 1.1],
            "close": [1.1, 1.2, 1.3],
            "volume": [100.0, 110.0, 120.0],
            "close_time": pd.date_range("2024-01-01", periods=3, freq="D", tz="UTC"),
        }
    )


def test_get_ohlcv_translates_timeframe_label_to_binance_interval():
    provider = RealDataProvider()
    with patch("confluence.data.providers.real_provider.fetch_klines", return_value=_fake_klines_df()) as mock_fetch:
        df = provider.get_ohlcv("XRPUSDT", "4H", limit=200)

    mock_fetch.assert_called_once_with("XRPUSDT", "4h", limit=200)
    assert len(df) == 3


def test_get_ohlcv_rejects_unknown_timeframe():
    provider = RealDataProvider()
    with pytest.raises(DataProviderError):
        provider.get_ohlcv("XRPUSDT", "5min")


def test_get_ohlcv_wraps_binance_errors():
    provider = RealDataProvider()
    with patch("confluence.data.providers.real_provider.fetch_klines", side_effect=BinanceAPIError("boom")):
        with pytest.raises(DataProviderError):
            provider.get_ohlcv("XRPUSDT", "1D")


def test_get_current_price_delegates_to_binance_client():
    provider = RealDataProvider()
    with patch("confluence.data.providers.real_provider.fetch_current_price", return_value=2.85) as mock_fetch:
        price = provider.get_current_price("XRPUSDT")

    mock_fetch.assert_called_once_with("XRPUSDT")
    assert price == pytest.approx(2.85)


def test_get_current_price_wraps_binance_errors():
    provider = RealDataProvider()
    with patch("confluence.data.providers.real_provider.fetch_current_price", side_effect=BinanceAPIError("boom")):
        with pytest.raises(DataProviderError):
            provider.get_current_price("XRPUSDT")
