from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import app


@pytest.fixture
def client(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        yield TestClient(app)


def test_get_watchlist_returns_default_tickers_with_screening_state(client):
    resp = client.get("/api/watchlist")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data_source"] == "mock"
    assert len(body["tickers"]) >= 1

    row = body["tickers"][0]
    assert row["ok"] is True
    assert row["current_price"] > 0
    assert row["alignment"] in {"aligned_bullish", "aligned_bearish", "conflict"}
    assert set(row["timeframes"]) == {"1D", "4H", "1H", "15min"}

    daily = row["timeframes"]["1D"]
    assert daily["ma_stack"] in {"bullish", "bearish", "mixed", "insufficient_data"}
    assert daily["rsi_zone"] in {"oversold", "neutral", "overbought", "insufficient_data"}
    assert daily["ma20_state"] in {"extended", "normal", "insufficient_data"}
    assert daily["volume_state"] in {"confirmed", "weak", "insufficient_data"}
    assert daily["rsi_divergence"] in {"none", "bullish", "bearish"}
    assert row["rr_ratio"] is None or row["rr_ratio"] > 0


def test_watchlist_response_includes_btc_reference_context(client):
    resp = client.get("/api/watchlist")
    body = resp.json()
    assert body["btc_context"]["symbol"] == "BTCUSDT"
    assert body["btc_context"]["ma_stack"] in {"bullish", "bearish", "mixed", "insufficient_data"}


def test_curated_bullish_ticker_shows_aligned_bullish(client):
    resp = client.post("/api/watchlist", json={"symbol": "XRPUSDT"})
    body = resp.json()
    row = next(r for r in body["tickers"] if r["symbol"] == "XRPUSDT")
    assert row["ok"] is True
    assert row["alignment"] == "aligned_bullish"


def test_curated_conflict_ticker_shows_conflict(client):
    resp = client.post("/api/watchlist", json={"symbol": "ADAUSDT"})
    body = resp.json()
    row = next(r for r in body["tickers"] if r["symbol"] == "ADAUSDT")
    assert row["ok"] is True
    assert row["alignment"] == "conflict"


def test_add_ticker_persists_and_appears_in_watchlist(client):
    resp = client.post("/api/watchlist", json={"symbol": "solusdt"})
    assert resp.status_code == 200
    symbols = [row["symbol"] for row in resp.json()["tickers"]]
    assert "SOLUSDT" in symbols

    resp2 = client.get("/api/watchlist")
    symbols2 = [row["symbol"] for row in resp2.json()["tickers"]]
    assert "SOLUSDT" in symbols2


def test_add_duplicate_ticker_does_not_duplicate_row(client):
    client.post("/api/watchlist", json={"symbol": "XRPUSDT"})
    resp = client.post("/api/watchlist", json={"symbol": "XRPUSDT"})
    symbols = [row["symbol"] for row in resp.json()["tickers"]]
    assert symbols.count("XRPUSDT") == 1


def test_add_ticker_rejects_blank_symbol(client):
    resp = client.post("/api/watchlist", json={"symbol": "   "})
    assert resp.status_code == 400


def test_remove_ticker_drops_it_from_watchlist(client):
    client.post("/api/watchlist", json={"symbol": "XRPUSDT"})
    resp = client.delete("/api/watchlist/XRPUSDT")
    assert resp.status_code == 200
    symbols = [row["symbol"] for row in resp.json()["tickers"]]
    assert "XRPUSDT" not in symbols


def test_remove_unknown_ticker_is_a_no_op(client):
    resp = client.delete("/api/watchlist/NOPEUSDT")
    assert resp.status_code == 200


def test_meta_reports_mock_data_source(client):
    resp = client.get("/api/meta")
    assert resp.status_code == 200
    assert resp.json() == {"data_source": "mock"}
