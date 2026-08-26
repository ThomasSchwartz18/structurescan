import numpy as np
import pandas as pd
import pytest

from confluence.indicators.enrich import enrich


def _synthetic_ohlcv(n=100, seed=0):
    rng = np.random.default_rng(seed)
    closes = 100 + np.cumsum(rng.normal(0, 1, n))
    highs = closes + rng.uniform(0.1, 1.0, n)
    lows = closes - rng.uniform(0.1, 1.0, n)
    volumes = rng.uniform(500, 1500, n)
    return pd.DataFrame(
        {
            "open_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
            "open": closes,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes,
            "close_time": pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC"),
        }
    )


def test_enrich_adds_atr_and_avg_volume_columns():
    df = enrich(_synthetic_ohlcv())
    assert "atr" in df.columns
    assert "avg_volume" in df.columns
    assert (df["atr"].dropna() >= 0).all()


def test_enrich_avg_volume_excludes_current_candle():
    df = _synthetic_ohlcv(n=30)
    # Make the very last candle's volume an extreme outlier; if avg_volume
    # included it, the average would shift, changing the expected value.
    df.loc[df.index[-1], "volume"] = 999_999.0
    enriched = enrich(df, volume_lookback=20)

    manual_avg = df["volume"].iloc[-21:-1].mean()  # trailing 20, excluding last row
    assert enriched["avg_volume"].iloc[-1] == pytest.approx(manual_avg)
    assert enriched["avg_volume"].iloc[-1] < 999_999.0


def test_enrich_avg_volume_nan_until_enough_history():
    df = enrich(_synthetic_ohlcv(n=30), volume_lookback=20)
    assert df["avg_volume"].iloc[:20].isna().all()
    assert df["avg_volume"].iloc[20:].notna().all()
