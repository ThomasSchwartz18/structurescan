import json
from unittest.mock import patch

from confluence.config import DEFAULT_TICKERS
from confluence.watchlist import load_tickers, save_tickers


def test_load_tickers_falls_back_to_defaults_when_no_file(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        assert load_tickers() == list(DEFAULT_TICKERS)


def test_save_then_load_round_trips(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        save_tickers(["BTCUSDT", "ETHUSDT"])
        assert load_tickers() == ["BTCUSDT", "ETHUSDT"]


def test_saved_empty_list_is_honored_not_reverted_to_defaults(tmp_path):
    # Regression: removing every ticker down to an empty watchlist must
    # stay empty, not silently snap back to DEFAULT_TICKERS.
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        save_tickers([])
        assert load_tickers() == []


def test_load_tickers_falls_back_on_corrupt_json(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    state_file.write_text("{not valid json")
    with patch("confluence.watchlist.STATE_FILE", state_file):
        assert load_tickers() == list(DEFAULT_TICKERS)


def test_load_tickers_falls_back_on_wrong_shape(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    state_file.write_text(json.dumps({"not": "a list"}))
    with patch("confluence.watchlist.STATE_FILE", state_file):
        assert load_tickers() == list(DEFAULT_TICKERS)
