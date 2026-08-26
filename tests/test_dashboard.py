import re

import pandas as pd
from rich.console import Console

from confluence.data.binance_client import BinanceAPIError
from confluence.output.dashboard import build_table
from confluence.screening.analysis import SwingRef, TickerReport, TimeframeState

FORBIDDEN_WORDS = [
    r"\bbuy\b",
    r"\bsell\b",
    r"\blong\b",
    r"\bshort\b",
    r"\bentry\b",
    r"\bexit\b",
    r"\brecommend",
    r"\bsignal\b",
]


def _render(table) -> str:
    console = Console(record=True, width=200)
    console.print(table)
    return console.export_text()


def _state(timeframe, ma_stack="bullish", structure="higher_highs_higher_lows", rsi=55.0, rsi_zone="neutral"):
    return TimeframeState(
        timeframe=timeframe,
        last_close=1.0,
        rsi=rsi,
        rsi_zone=rsi_zone,
        ma_values={20: 4, 50: 3, 100: 2, 200: 1},
        ma_stack=ma_stack,
        price_vs_ma={20: "above", 50: "above", 100: "above", 200: "above"},
        structure=structure,
        nearest_swing_high=SwingRef(open_time=pd.Timestamp("2024-06-01", tz="UTC"), price=1.2345),
        nearest_swing_low=SwingRef(open_time=pd.Timestamp("2024-05-01", tz="UTC"), price=0.9876),
        bias_state="bullish_state" if ma_stack == "bullish" else "bearish_state",
    )


def test_build_table_renders_expected_fields():
    report = TickerReport(
        symbol="XRPUSDT",
        timeframes={
            "1D": _state("1D"),
            "4H": _state("4H"),
            "1H": _state("1H"),
            "15min": _state("15min"),
        },
        alignment="aligned_bullish",
    )

    text = _render(build_table({"XRPUSDT": report}))

    assert "XRPUSDT" in text
    assert "bullish" in text
    assert "55.0" in text and "neutral" in text
    assert "HH/HL" in text
    assert "1.2345" in text
    assert "0.9876" in text
    assert "aligned" in text


def test_build_table_handles_fetch_error_rows():
    error = BinanceAPIError("boom")
    text = _render(build_table({"BADPAIR": error}))
    assert "BADPAIR" in text
    assert "error" in text
    assert "boom" in text


def test_build_table_never_emits_trading_action_language():
    report = TickerReport(
        symbol="XRPUSDT",
        timeframes={"1D": _state("1D"), "4H": _state("4H", ma_stack="bearish", structure="lower_highs_lower_lows")},
        alignment="conflict",
    )
    text = _render(build_table({"XRPUSDT": report})).lower()
    # Drop the title line: it deliberately contains "recommendation" as a
    # disclaimer ("...descriptive only, not a recommendation"). We only
    # want to police the data cells themselves.
    body = "\n".join(text.splitlines()[1:])

    for pattern in FORBIDDEN_WORDS:
        assert not re.search(pattern, body), f"dashboard output contains forbidden phrase matching {pattern!r}"
