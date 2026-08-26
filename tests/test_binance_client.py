from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from confluence.data.binance_client import BinanceAPIError, fetch_current_price, fetch_klines


def _kline_row(open_time_ms, o, h, l, c, v, close_time_ms):
    return [
        open_time_ms,
        str(o),
        str(h),
        str(l),
        str(c),
        str(v),
        close_time_ms,
        "0",   # quote_asset_volume
        1,     # num_trades
        "0",   # taker_buy_base_volume
        "0",   # taker_buy_quote_volume
        "0",   # ignore
    ]


def _make_response(rows):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = rows
    return resp


DAY_MS = 24 * 60 * 60 * 1000


def test_fetch_klines_parses_closed_candles():
    now = pd.Timestamp.now(tz="UTC")
    now_ms = int(now.timestamp() * 1000)

    # Two fully closed daily candles, oldest first.
    rows = [
        _kline_row(now_ms - 3 * DAY_MS, 1.0, 1.2, 0.9, 1.1, 1000, now_ms - 2 * DAY_MS - 1),
        _kline_row(now_ms - 2 * DAY_MS, 1.1, 1.3, 1.0, 1.2, 1500, now_ms - 1 * DAY_MS - 1),
    ]

    with patch("confluence.data.binance_client.requests.get", return_value=_make_response(rows)):
        df = fetch_klines("XRPUSDT", "1d", limit=2)

    assert list(df.columns) == ["open_time", "open", "high", "low", "close", "volume", "close_time"]
    assert len(df) == 2
    assert df["close"].tolist() == [1.1, 1.2]
    assert df["open"].dtype == float
    assert pd.api.types.is_datetime64_any_dtype(df["open_time"])


def test_fetch_klines_drops_unclosed_final_candle():
    now = pd.Timestamp.now(tz="UTC")
    now_ms = int(now.timestamp() * 1000)

    rows = [
        _kline_row(now_ms - 2 * DAY_MS, 1.0, 1.2, 0.9, 1.1, 1000, now_ms - 1 * DAY_MS - 1),
        # Still-forming candle: close_time in the future.
        _kline_row(now_ms, 1.1, 1.3, 1.0, 1.25, 500, now_ms + DAY_MS),
    ]

    with patch("confluence.data.binance_client.requests.get", return_value=_make_response(rows)):
        df = fetch_klines("XRPUSDT", "1d", limit=2, drop_unclosed=True)

    assert len(df) == 1
    assert df["close"].iloc[0] == 1.1


def test_fetch_klines_keeps_unclosed_when_disabled():
    now = pd.Timestamp.now(tz="UTC")
    now_ms = int(now.timestamp() * 1000)

    rows = [
        _kline_row(now_ms, 1.1, 1.3, 1.0, 1.25, 500, now_ms + DAY_MS),
    ]

    with patch("confluence.data.binance_client.requests.get", return_value=_make_response(rows)):
        df = fetch_klines("XRPUSDT", "1d", limit=1, drop_unclosed=False)

    assert len(df) == 1


def test_fetch_klines_raises_on_non_200():
    resp = MagicMock()
    resp.status_code = 451
    resp.text = "restricted location"

    with patch("confluence.data.binance_client.requests.get", return_value=resp):
        with pytest.raises(BinanceAPIError):
            fetch_klines("XRPUSDT", "1d")


def test_fetch_klines_raises_on_empty_body():
    with patch("confluence.data.binance_client.requests.get", return_value=_make_response([])):
        with pytest.raises(BinanceAPIError):
            fetch_klines("XRPUSDT", "1d")


def _price_response(price):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"symbol": "XRPUSDT", "price": str(price)}
    return resp


def test_fetch_current_price_parses_price():
    with patch("confluence.data.binance_client.requests.get", return_value=_price_response("2.85000000")):
        price = fetch_current_price("XRPUSDT")
    assert price == pytest.approx(2.85)


def test_fetch_current_price_raises_on_non_200():
    resp = MagicMock()
    resp.status_code = 451
    resp.text = "restricted location"
    with patch("confluence.data.binance_client.requests.get", return_value=resp):
        with pytest.raises(BinanceAPIError):
            fetch_current_price("XRPUSDT")


def test_fetch_current_price_raises_on_unexpected_body():
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {"unexpected": "shape"}
    with patch("confluence.data.binance_client.requests.get", return_value=resp):
        with pytest.raises(BinanceAPIError):
            fetch_current_price("XRPUSDT")
