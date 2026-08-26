from unittest.mock import patch

import numpy as np
import pandas as pd

from confluence.data.binance_client import BinanceAPIError
from confluence.indicators.enrich import enrich
from confluence.main import build_reports
from confluence.screening.analysis import TickerReport


def _synthetic_ohlcv(n=260, seed=1):
    rng = np.random.default_rng(seed)
    closes = np.linspace(100, 150, n) + rng.normal(0, 1.0, n)
    return pd.DataFrame(
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


def test_build_reports_mixes_success_and_failure():
    good_df = enrich(_synthetic_ohlcv())
    fake_universe = {
        "GOODUSDT": {"1D": good_df, "4H": good_df},
        "BADUSDT": BinanceAPIError("symbol not found"),
    }

    with patch("confluence.main.fetch_universe", return_value=fake_universe):
        reports = build_reports(["GOODUSDT", "BADUSDT"])

    assert isinstance(reports["GOODUSDT"], TickerReport)
    assert reports["GOODUSDT"].symbol == "GOODUSDT"
    assert isinstance(reports["BADUSDT"], BinanceAPIError)
