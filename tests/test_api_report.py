from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import app


@pytest.fixture
def client(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    with patch("confluence.watchlist.STATE_FILE", state_file):
        yield TestClient(app)


def test_report_ranks_curated_tickers_highest_first(client):
    for symbol in ["XRPUSDT", "HYPEUSD", "SOLUSDT", "ADAUSDT", "DOGEUSDT"]:
        client.post("/api/watchlist", json={"symbol": symbol})

    resp = client.get("/api/report")
    assert resp.status_code == 200
    body = resp.json()

    assert body["data_source"] == "mock"
    symbols = [s["symbol"] for s in body["scores"]]
    assert set(symbols) == {"XRPUSDT", "HYPEUSD", "SOLUSDT", "ADAUSDT", "DOGEUSDT"}

    met_counts = [s["met_count"] for s in body["scores"]]
    assert met_counts == sorted(met_counts, reverse=True)  # ranked highest first

    for score in body["scores"]:
        assert score["total_count"] == 6
        assert len(score["criteria"]) == 6
        for criterion in score["criteria"]:
            assert set(criterion) == {"key", "label", "met"}


def test_report_never_emits_recommendation_language(client):
    client.post("/api/watchlist", json={"symbol": "XRPUSDT"})
    resp = client.get("/api/report")
    text = resp.text.lower()

    for phrase in ["focus on", "best setup", "top pick", " buy ", " sell "]:
        assert phrase not in text


def test_report_excludes_symbols_that_fail_to_fetch(client):
    with patch("confluence.api.routes.report.fetch_universe_from_provider") as mock_fetch:
        mock_fetch.return_value = {"BADUSDT": RuntimeError("boom")}
        with patch("confluence.api.routes.report.load_tickers", return_value=["BADUSDT"]):
            resp = client.get("/api/report")

    body = resp.json()
    assert body["scores"] == []
    assert body["failed_symbols"] == ["BADUSDT"]


def test_report_empty_watchlist_returns_empty_scores(client):
    with patch("confluence.api.routes.report.load_tickers", return_value=[]):
        resp = client.get("/api/report")
    body = resp.json()
    assert body["scores"] == []
    assert body["failed_symbols"] == []
