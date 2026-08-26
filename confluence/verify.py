"""Quick manual sanity check: fetch one symbol/timeframe and print indicator
values so they can be eyeballed against TradingView.

Usage:
    python -m confluence.verify XRPUSDT 1D
"""

from __future__ import annotations

import sys

import pandas as pd

from confluence.config import CANDLE_LIMIT, RSI_PERIOD, SMA_PERIODS, TIMEFRAMES
from confluence.data.binance_client import fetch_klines
from confluence.indicators.ta import rsi, sma


def build_indicator_table(symbol: str, timeframe_label: str) -> pd.DataFrame:
    interval = TIMEFRAMES[timeframe_label]
    df = fetch_klines(symbol, interval, limit=CANDLE_LIMIT)

    df["rsi14"] = rsi(df["close"], RSI_PERIOD)
    for period in SMA_PERIODS:
        df[f"sma{period}"] = sma(df["close"], period)

    return df


def main() -> None:
    symbol = sys.argv[1] if len(sys.argv) > 1 else "XRPUSDT"
    timeframe_label = sys.argv[2] if len(sys.argv) > 2 else "1D"

    if timeframe_label not in TIMEFRAMES:
        raise SystemExit(f"unknown timeframe '{timeframe_label}', pick from {list(TIMEFRAMES)}")

    df = build_indicator_table(symbol, timeframe_label)

    display_cols = ["open_time", "close", "rsi14"] + [f"sma{p}" for p in SMA_PERIODS]
    tail = df[display_cols].tail(10).copy()
    tail["open_time"] = tail["open_time"].dt.strftime("%Y-%m-%d %H:%M")
    for col in ["close", "rsi14"] + [f"sma{p}" for p in SMA_PERIODS]:
        tail[col] = tail[col].map(lambda v: f"{v:.4f}" if pd.notna(v) else "n/a")

    print(f"\n{symbol} {timeframe_label} — last {len(tail)} closed candles\n")
    print(tail.to_string(index=False))
    print(
        f"\nMost recent closed candle: {df['open_time'].iloc[-1]} "
        f"(close_time={df['close_time'].iloc[-1]})"
    )


if __name__ == "__main__":
    main()
