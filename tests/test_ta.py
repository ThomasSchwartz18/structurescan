import math

import pandas as pd
import pytest

from confluence.indicators.ta import rsi, sma


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
