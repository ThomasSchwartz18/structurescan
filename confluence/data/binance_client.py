"""Thin client for Binance's public market-data REST API (no auth required)."""

from __future__ import annotations

import datetime as dt

import pandas as pd
import requests

BASE_URL = "https://api.binance.com"
KLINES_ENDPOINT = "/api/v3/klines"
TICKER_PRICE_ENDPOINT = "/api/v3/ticker/price"

COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "num_trades",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
    "ignore",
]

NUMERIC_COLUMNS = [
    "open",
    "high",
    "low",
    "close",
    "volume",
    "quote_asset_volume",
    "taker_buy_base_volume",
    "taker_buy_quote_volume",
]


class BinanceAPIError(RuntimeError):
    """Raised when Binance returns a non-2xx response or an unexpected body."""


def fetch_klines(
    symbol: str,
    interval: str,
    limit: int = 300,
    *,
    drop_unclosed: bool = True,
    timeout: float = 10.0,
) -> pd.DataFrame:
    """Fetch OHLCV candles for a symbol/interval from Binance spot market data.

    Parameters
    ----------
    symbol: e.g. "XRPUSDT"
    interval: Binance interval code, e.g. "1d", "4h", "1h", "15m"
    limit: number of candles to request (Binance max is 1000)
    drop_unclosed: drop the most recent candle if it hasn't closed yet, so
        indicator values match what charting tools show for completed bars.

    Returns a DataFrame indexed by open_time (UTC), sorted oldest -> newest.
    """
    params = {"symbol": symbol.upper(), "interval": interval, "limit": limit}
    try:
        resp = requests.get(BASE_URL + KLINES_ENDPOINT, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise BinanceAPIError(f"request failed for {symbol} {interval}: {exc}") from exc

    if resp.status_code != 200:
        raise BinanceAPIError(
            f"Binance returned HTTP {resp.status_code} for {symbol} {interval}: {resp.text}"
        )

    raw = resp.json()
    if not isinstance(raw, list) or not raw:
        raise BinanceAPIError(f"unexpected/empty response for {symbol} {interval}: {raw}")

    df = pd.DataFrame(raw, columns=COLUMNS)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms", utc=True)
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms", utc=True)
    df[NUMERIC_COLUMNS] = df[NUMERIC_COLUMNS].astype(float)
    df["num_trades"] = df["num_trades"].astype(int)

    df = df[["open_time", "open", "high", "low", "close", "volume", "close_time"]]

    if drop_unclosed:
        now = pd.Timestamp.now(tz="UTC")
        df = df[df["close_time"] <= now]

    df = df.reset_index(drop=True)
    return df


def fetch_current_price(symbol: str, *, timeout: float = 10.0) -> float:
    """Latest traded price for `symbol` from Binance's public ticker
    endpoint — no auth required, same as fetch_klines."""
    params = {"symbol": symbol.upper()}
    try:
        resp = requests.get(BASE_URL + TICKER_PRICE_ENDPOINT, params=params, timeout=timeout)
    except requests.RequestException as exc:
        raise BinanceAPIError(f"request failed for {symbol} price: {exc}") from exc

    if resp.status_code != 200:
        raise BinanceAPIError(f"Binance returned HTTP {resp.status_code} for {symbol} price: {resp.text}")

    raw = resp.json()
    if not isinstance(raw, dict) or "price" not in raw:
        raise BinanceAPIError(f"unexpected response for {symbol} price: {raw}")

    return float(raw["price"])
