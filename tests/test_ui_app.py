import time
from unittest.mock import patch

import pytest

from confluence.data.binance_client import BinanceAPIError
from confluence.screening.analysis import SwingRef, TickerReport, TimeframeState

tk = pytest.importorskip("tkinter")


def _tk_available() -> bool:
    try:
        root = tk.Tk()
        root.destroy()
        return True
    except tk.TclError:
        return False


pytestmark = pytest.mark.skipif(not _tk_available(), reason="no display available for Tk")


def _state(timeframe, ma_stack="bullish", structure="higher_highs_higher_lows"):
    return TimeframeState(
        timeframe=timeframe,
        last_close=1.0,
        rsi=55.0,
        rsi_zone="neutral",
        ma_values={20: 4, 50: 3, 100: 2, 200: 1},
        ma_stack=ma_stack,
        price_vs_ma={20: "above", 50: "above", 100: "above", 200: "above"},
        structure=structure,
        nearest_swing_high=SwingRef(open_time="2024-06-01", price=1.5),
        nearest_swing_low=SwingRef(open_time="2024-05-01", price=0.5),
        bias_state="bullish_state" if ma_stack == "bullish" else "bearish_state",
    )


def _wait_until(app, predicate, timeout=2.0):
    # Tk's `after` callbacks (including the queue poller) only fire while
    # the event loop is being pumped, so each wait tick must call update().
    deadline = time.time() + timeout
    while time.time() < deadline:
        app.update()
        if predicate():
            return True
        time.sleep(0.05)
    return False


@pytest.fixture
def isolated_state(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.ui.state.STATE_FILE", state_file):
        yield state_file


def test_app_populates_rows_from_mocked_fetch(isolated_state):
    from confluence.ui.app import ConfluenceApp

    good_report = TickerReport(
        symbol="XRPUSDT",
        timeframes={"1D": _state("1D"), "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")},
        alignment="aligned_bullish",
    )
    fake_reports = {"XRPUSDT": good_report, "BADUSDT": BinanceAPIError("boom")}

    with patch("confluence.ui.app.load_tickers", return_value=["XRPUSDT", "BADUSDT"]), \
         patch("confluence.ui.app.save_tickers"), \
         patch("confluence.ui.app.build_reports", return_value=fake_reports):
        app = ConfluenceApp()
        try:
            app.update()
            assert _wait_until(app, lambda: app.tree.item("XRPUSDT")["values"][0] != "fetching...", timeout=3)

            good_values = app.tree.item("XRPUSDT")["values"]
            assert good_values[0] == "bullish"
            assert "aligned" in good_values[-1]

            bad_values = app.tree.item("BADUSDT")["values"]
            assert "error" in bad_values[0]
            assert "boom" in bad_values[0]
        finally:
            app.destroy()


def test_add_and_remove_ticker_updates_tree_and_state(isolated_state):
    from confluence.ui.app import ConfluenceApp

    with patch("confluence.ui.app.load_tickers", return_value=["XRPUSDT"]), \
         patch("confluence.ui.app.save_tickers") as mock_save, \
         patch("confluence.ui.app.build_reports", return_value={"XRPUSDT": BinanceAPIError("n/a")}):
        app = ConfluenceApp()
        try:
            app.update()

            app.ticker_entry.insert(0, "btcusdt")
            app._add_ticker()
            app.update()
            assert "BTCUSDT" in app.tickers
            assert app.tree.exists("BTCUSDT")
            mock_save.assert_called_with(app.tickers)

            app.tree.selection_set("BTCUSDT")
            app._remove_selected()
            app.update()
            assert "BTCUSDT" not in app.tickers
            assert not app.tree.exists("BTCUSDT")
        finally:
            app.destroy()


def test_refresh_interval_validation_rejects_bad_input(isolated_state):
    from confluence.ui.app import ConfluenceApp, MIN_REFRESH_SECONDS

    with patch("confluence.ui.app.load_tickers", return_value=["XRPUSDT"]), \
         patch("confluence.ui.app.save_tickers"), \
         patch("confluence.ui.app.build_reports", return_value={"XRPUSDT": BinanceAPIError("n/a")}), \
         patch("confluence.ui.app.messagebox.showerror") as mock_error:
        app = ConfluenceApp()
        try:
            app.update()
            app.refresh_entry.delete(0, tk.END)
            app.refresh_entry.insert(0, "1")  # below MIN_REFRESH_SECONDS
            app._apply_refresh_interval()
            mock_error.assert_called_once()
            assert app.refresh_seconds != 1
        finally:
            app.destroy()
