import pandas as pd

from confluence.indicators.swings import find_swings, nearest_swings, swing_sequence


def _make_df(highs, lows):
    n = len(highs)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": highs,   # not used by swing detection; placeholder
            "high": highs,
            "low": lows,
            "close": highs,
            "volume": [1.0] * n,
            "close_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        }
    )


def test_find_swings_marks_expected_fractals():
    highs = [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]
    lows = [5, 4, 3, 4, 5, 4, 3, 2, 3, 4]
    df = find_swings(_make_df(highs, lows), order=1)

    assert df["swing_high"].tolist() == [
        False, False, True, False, False, False, False, True, False, False
    ]
    assert df["swing_low"].tolist() == [
        False, False, True, False, False, False, False, True, False, False
    ]


def test_swing_sequence_chronological_order():
    highs = [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]
    lows = [5, 4, 3, 4, 5, 4, 3, 2, 3, 4]
    df = find_swings(_make_df(highs, lows), order=1)

    seq = swing_sequence(df, "high")
    assert len(seq) == 2
    assert seq["price"].tolist() == [3, 4]
    assert seq["open_time"].iloc[0] < seq["open_time"].iloc[1]


def test_nearest_swings_returns_most_recent_confirmed():
    highs = [1, 2, 3, 2, 1, 2, 3, 4, 3, 2]
    lows = [5, 4, 3, 4, 5, 4, 3, 2, 3, 4]
    df = find_swings(_make_df(highs, lows), order=1)

    nearest = nearest_swings(df)
    assert nearest["swing_high"]["price"] == 4
    assert nearest["swing_low"]["price"] == 2


def test_nearest_swings_none_when_no_confirmed_points():
    # Monotonically increasing highs/lows never form an interior fractal.
    highs = [1, 2, 3, 4, 5]
    lows = [1, 2, 3, 4, 5]
    df = find_swings(_make_df(highs, lows), order=2)

    nearest = nearest_swings(df)
    assert nearest["swing_high"] is None
    assert nearest["swing_low"] is None


def test_find_swings_rejects_invalid_order():
    import pytest

    df = _make_df([1, 2, 3], [1, 2, 3])
    with pytest.raises(ValueError):
        find_swings(df, order=0)
