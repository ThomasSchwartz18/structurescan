import numpy as np
import pandas as pd
import pytest

from confluence.indicators.enrich import enrich
from confluence.screening.analysis import (
    SwingRef,
    TimeframeState,
    build_ticker_report,
    build_timeframe_state,
    candles_since_swing,
    classify_ma20_distance,
    classify_ma_stack,
    classify_rsi_zone,
    classify_structure,
    classify_volume,
    compute_extension_ratio,
    compute_rr_ratio,
    detect_rsi_divergence,
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


@pytest.mark.parametrize(
    "close,ma20,expected_pct,expected_state",
    [
        (105.0, 100.0, 5.0, "normal"),       # exactly at the 5% threshold -> not strictly beyond it
        (106.0, 100.0, 6.0, "extended"),
        (95.0, 100.0, -5.0, "normal"),
        (94.0, 100.0, -6.0, "extended"),      # extension is symmetric: works below the MA too
        (100.0, 100.0, 0.0, "normal"),
    ],
)
def test_classify_ma20_distance(close, ma20, expected_pct, expected_state):
    pct, state = classify_ma20_distance(close, ma20)
    assert pct == pytest.approx(expected_pct)
    assert state == expected_state


def test_classify_ma20_distance_insufficient_data():
    assert classify_ma20_distance(100.0, None) == (None, "insufficient_data")
    assert classify_ma20_distance(100.0, 0.0) == (None, "insufficient_data")


@pytest.mark.parametrize(
    "last_volume,avg_volume,expected_ratio,expected_state",
    [
        (150.0, 100.0, 1.5, "confirmed"),
        (50.0, 100.0, 0.5, "weak"),
        (100.0, 100.0, 1.0, "confirmed"),  # exactly average counts as confirmed, not weak
    ],
)
def test_classify_volume(last_volume, avg_volume, expected_ratio, expected_state):
    ratio, state = classify_volume(last_volume, avg_volume)
    assert ratio == pytest.approx(expected_ratio)
    assert state == expected_state


def test_classify_volume_insufficient_data():
    assert classify_volume(100.0, None) == (None, "insufficient_data")
    assert classify_volume(100.0, 0.0) == (None, "insufficient_data")


def test_compute_extension_ratio():
    swing_low = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=100.0)
    assert compute_extension_ratio(110.0, swing_low, 5.0) == pytest.approx(2.0)
    assert compute_extension_ratio(90.0, swing_low, 5.0) == pytest.approx(-2.0)


def test_compute_extension_ratio_missing_inputs():
    swing_low = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=100.0)
    assert compute_extension_ratio(110.0, None, 5.0) is None
    assert compute_extension_ratio(110.0, swing_low, None) is None
    assert compute_extension_ratio(110.0, swing_low, 0.0) is None


def _divergence_df(swing_high_rows, swing_low_rows, n=8):
    df = pd.DataFrame(
        {
            "high": [0.0] * n,
            "low": [0.0] * n,
            "rsi": [50.0] * n,
            "swing_high": [False] * n,
            "swing_low": [False] * n,
        }
    )
    for idx, price, rsi_val in swing_high_rows:
        df.loc[idx, "swing_high"] = True
        df.loc[idx, "high"] = price
        df.loc[idx, "rsi"] = rsi_val
    for idx, price, rsi_val in swing_low_rows:
        df.loc[idx, "swing_low"] = True
        df.loc[idx, "low"] = price
        df.loc[idx, "rsi"] = rsi_val
    return df


def test_detect_rsi_divergence_bullish():
    # Price makes a lower low, RSI makes a higher low.
    df = _divergence_df(swing_high_rows=[], swing_low_rows=[(2, 50.0, 40.0), (5, 45.0, 45.0)])
    assert detect_rsi_divergence(df) == "bullish"


def test_detect_rsi_divergence_bearish():
    # Price makes a higher high, RSI makes a lower high.
    df = _divergence_df(swing_high_rows=[(2, 100.0, 70.0), (5, 110.0, 60.0)], swing_low_rows=[])
    assert detect_rsi_divergence(df) == "bearish"


def test_detect_rsi_divergence_none_when_price_and_rsi_agree():
    # Higher low in price AND higher low in RSI -> no divergence.
    df = _divergence_df(swing_high_rows=[], swing_low_rows=[(2, 50.0, 40.0), (5, 55.0, 45.0)])
    assert detect_rsi_divergence(df) == "none"


def test_detect_rsi_divergence_none_with_insufficient_swings():
    df = _divergence_df(swing_high_rows=[], swing_low_rows=[(2, 50.0, 40.0)])
    assert detect_rsi_divergence(df) == "none"


def test_candles_since_swing_counts_from_most_recent_flag():
    df = pd.DataFrame({"swing_high": [False] * 10, "swing_low": [False] * 10})
    df.loc[6, "swing_high"] = True
    df.loc[2, "swing_low"] = True
    df.loc[8, "swing_low"] = True  # most recent low

    assert candles_since_swing(df, "high") == 3   # (10-1) - 6
    assert candles_since_swing(df, "low") == 1    # (10-1) - 8


def test_candles_since_swing_none_when_never_confirmed():
    df = pd.DataFrame({"swing_high": [False] * 5, "swing_low": [False] * 5})
    assert candles_since_swing(df, "high") is None


def test_compute_rr_ratio():
    high = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=110.0)
    low = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=95.0)
    assert compute_rr_ratio(100.0, high, low) == pytest.approx(10.0 / 5.0)


def test_compute_rr_ratio_missing_swings():
    low = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=95.0)
    assert compute_rr_ratio(100.0, None, low) is None


def test_compute_rr_ratio_zero_support_distance_is_none():
    high = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=110.0)
    low = SwingRef(open_time=pd.Timestamp("2024-01-01", tz="UTC"), price=100.0)
    assert compute_rr_ratio(100.0, high, low) is None  # current price == support price


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
    assert report.rr_ratio is None or report.rr_ratio > 0
    for state in report.timeframes.values():
        assert state.ma_stack in {"bullish", "bearish", "mixed", "insufficient_data"}
        assert state.rsi_zone in {"oversold", "neutral", "overbought", "insufficient_data"}
        assert state.ma20_state in {"extended", "normal", "insufficient_data"}
        assert state.volume_state in {"confirmed", "weak", "insufficient_data"}
        assert state.rsi_divergence in {"none", "bullish", "bearish"}
        assert state.atr is None or state.atr >= 0
        assert state.candles_since_swing_high is None or state.candles_since_swing_high >= 0
        assert state.candles_since_swing_low is None or state.candles_since_swing_low >= 0
