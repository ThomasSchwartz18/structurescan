import math

import pandas as pd
import pytest

from confluence.indicators.ta import atr, rsi, sma, true_range


def test_sma_basic():
    s = pd.Series([1, 2, 3, 4, 5])
    result = sma(s, period=3)
    assert math.isnan(result.iloc[0])
    assert math.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)   # mean(1,2,3)
    assert result.iloc[3] == pytest.approx(3.0)   # mean(2,3,4)
    assert result.iloc[4] == pytest.approx(4.0)   # mean(3,4,5)


def test_rsi_hand_computed_period_3():
    # Hand-computed via Wilder's method (SMA-seeded recursive smoothing),
    # the same method TradingView's built-in RSI uses.
    closes = pd.Series([44.00, 44.25, 44.50, 43.75, 44.50, 44.25, 44.50])
    result = rsi(closes, period=3)

    assert result.iloc[:3].isna().all()

    expected = {
        3: 40.00,
        4: 68.42,
        5: 55.32,
        6: 65.29,
    }
    for idx, expected_value in expected.items():
        assert result.iloc[idx] == pytest.approx(expected_value, abs=0.01)


def test_rsi_all_gains_is_100():
    closes = pd.Series([float(i) for i in range(1, 20)])  # strictly increasing
    result = rsi(closes, period=14)
    assert result.iloc[-1] == pytest.approx(100.0)


def test_rsi_all_losses_is_0():
    closes = pd.Series([float(i) for i in range(20, 1, -1)])  # strictly decreasing
    result = rsi(closes, period=14)
    assert result.iloc[-1] == pytest.approx(0.0)


def test_rsi_too_short_series_is_all_nan():
    closes = pd.Series([1.0, 2.0, 3.0])
    result = rsi(closes, period=14)
    assert result.isna().all()


def _ohlc_df(highs, lows, closes):
    return pd.DataFrame({"high": highs, "low": lows, "close": closes})


def test_true_range_first_bar_has_no_prior_close():
    df = _ohlc_df([10], [8], [9])
    result = true_range(df)
    assert result.iloc[0] == pytest.approx(2.0)  # just high - low


def test_true_range_hand_computed():
    # bar1: gap up from prior close (9) to a 9-11 range -> |11-9| dominates
    # bar2: inside bar relative to prior close -> high-low dominates
    highs = [10, 11, 12, 11, 13]
    lows = [8, 9, 10, 9, 10]
    closes = [9, 10, 11, 10, 12]
    df = _ohlc_df(highs, lows, closes)
    result = true_range(df)

    expected = [2, 2, 2, 2, 3]
    for i, exp in enumerate(expected):
        assert result.iloc[i] == pytest.approx(float(exp))


def test_atr_hand_computed_period_3():
    highs = [10, 11, 12, 11, 13]
    lows = [8, 9, 10, 9, 10]
    closes = [9, 10, 11, 10, 12]
    df = _ohlc_df(highs, lows, closes)
    result = atr(df, period=3)

    assert result.iloc[:2].isna().all()
    # seed at index 2 = mean(TR[0:3]) = mean(2,2,2) = 2.0
    assert result.iloc[2] == pytest.approx(2.0)
    # index 3 = (2.0*2 + TR[3]=2) / 3 = 2.0
    assert result.iloc[3] == pytest.approx(2.0)
    # index 4 = (2.0*2 + TR[4]=3) / 3 = 2.3333...
    assert result.iloc[4] == pytest.approx(7 / 3)


def test_atr_too_short_series_is_all_nan():
    df = _ohlc_df([10, 11], [8, 9], [9, 10])
    result = atr(df, period=14)
    assert result.isna().all()


def test_atr_is_non_negative_on_synthetic_data():
    import numpy as np

    rng = np.random.default_rng(0)
    n = 100
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    highs = closes + rng.uniform(0.1, 1.0, n)
    lows = closes - rng.uniform(0.1, 1.0, n)
    df = _ohlc_df(highs, lows, closes)
    result = atr(df, period=14)
    assert (result.dropna() >= 0).all()
