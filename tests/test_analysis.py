import numpy as np
import pandas as pd
import pytest

from confluence.indicators.enrich import enrich
from confluence.screening.analysis import (
    TimeframeState,
    build_ticker_report,
    build_timeframe_state,
    classify_ma_stack,
    classify_rsi_zone,
    classify_structure,
    determine_alignment,
)


def test_classify_ma_stack_bullish():
    assert classify_ma_stack({20: 4, 50: 3, 100: 2, 200: 1}) == "bullish"


def test_classify_ma_stack_bearish():
    assert classify_ma_stack({20: 1, 50: 2, 100: 3, 200: 4}) == "bearish"


def test_classify_ma_stack_mixed():
    assert classify_ma_stack({20: 3, 50: 4, 100: 2, 200: 1}) == "mixed"


def test_classify_ma_stack_insufficient_data():
    assert classify_ma_stack({20: 3, 50: None, 100: 2, 200: 1}) == "insufficient_data"


@pytest.mark.parametrize(
    "value,expected",
    [(85.0, "overbought"), (70.0, "overbought"), (69.9, "neutral"), (50.0, "neutral"),
     (30.0, "oversold"), (30.1, "neutral"), (10.0, "oversold")],
)
def test_classify_rsi_zone(value, expected):
    assert classify_rsi_zone(value) == expected


def test_classify_rsi_zone_insufficient_data():
    assert classify_rsi_zone(None) == "insufficient_data"


def _swing_df(swing_high_rows, swing_low_rows, n=6):
    df = pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "high": [0.0] * n,
            "low": [0.0] * n,
            "swing_high": [False] * n,
            "swing_low": [False] * n,
        }
    )
    for idx, price in swing_high_rows:
        df.loc[idx, "swing_high"] = True
        df.loc[idx, "high"] = price
    for idx, price in swing_low_rows:
        df.loc[idx, "swing_low"] = True
        df.loc[idx, "low"] = price
    return df


def test_classify_structure_higher_highs_higher_lows():
    df = _swing_df(swing_high_rows=[(1, 10), (4, 15)], swing_low_rows=[(2, 5), (3, 8)])
    assert classify_structure(df) == "higher_highs_higher_lows"


def test_classify_structure_lower_highs_lower_lows():
    df = _swing_df(swing_high_rows=[(1, 15), (4, 10)], swing_low_rows=[(2, 8), (3, 5)])
    assert classify_structure(df) == "lower_highs_lower_lows"


def test_classify_structure_mixed():
    # Higher high but lower low -> not a clean trend structure.
    df = _swing_df(swing_high_rows=[(1, 10), (4, 15)], swing_low_rows=[(2, 8), (3, 5)])
    assert classify_structure(df) == "mixed"


def test_classify_structure_insufficient_data():
    df = _swing_df(swing_high_rows=[(1, 10)], swing_low_rows=[(2, 5)])
    assert classify_structure(df) == "insufficient_data"


def test_determine_alignment_all_bullish():
    states = {
        "1D": TimeframeState("1D", 1, None, "neutral", {}, "bullish", {}, "higher_highs_higher_lows", None, None, "bullish_state"),
        "4H": TimeframeState("4H", 1, None, "neutral", {}, "bullish", {}, "higher_highs_higher_lows", None, None, "bullish_state"),
    }
    assert determine_alignment(states) == "aligned_bullish"


def test_determine_alignment_conflict():
    states = {
        "1D": TimeframeState("1D", 1, None, "neutral", {}, "bullish", {}, "higher_highs_higher_lows", None, None, "bullish_state"),
        "4H": TimeframeState("4H", 1, None, "neutral", {}, "bearish", {}, "lower_highs_lower_lows", None, None, "bearish_state"),
    }
    assert determine_alignment(states) == "conflict"


def test_build_ticker_report_end_to_end_smoke():
    # Enough candles for SMA200 + swing confirmation; strictly uptrending
    # with noise so swing highs/lows actually form.
    rng = np.random.default_rng(42)
    n = 260
    trend = np.linspace(100, 200, n)
    noise = rng.normal(0, 1.5, n)
    closes = trend + noise

    base = pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": closes,
            "high": closes + 1,
            "low": closes - 1,
            "close": closes,
            "volume": np.full(n, 1000.0),
            "close_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        }
    )
    enriched = enrich(base)

    report = build_ticker_report("TESTUSDT", {"1D": enriched, "4H": enriched})

    assert report.symbol == "TESTUSDT"
    assert set(report.timeframes) == {"1D", "4H"}
    assert report.alignment in {"aligned_bullish", "aligned_bearish", "conflict"}
    for state in report.timeframes.values():
        assert state.ma_stack in {"bullish", "bearish", "mixed", "insufficient_data"}
        assert state.rsi_zone in {"oversold", "neutral", "overbought", "insufficient_data"}
