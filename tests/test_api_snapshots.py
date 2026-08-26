from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import app
from confluence.screening.analysis import TickerReport, TimeframeState
from confluence.snapshots.db import get_connection
from confluence.snapshots.store import save_snapshot


@pytest.fixture
def client(tmp_path):
    snapshots_file = tmp_path / "snapshots.db"
    with patch("confluence.snapshots.db.DB_FILE", snapshots_file):
        yield TestClient(app)


def _report(symbol="XRPUSDT"):
    state = TimeframeState(
        timeframe="1D",
        last_close=2.85,
        rsi=55.0,
        rsi_zone="neutral",
        ma_values={20: 2.8, 50: 2.7, 100: 2.6, 200: 2.5},
        ma_stack="bullish",
        price_vs_ma={20: "above", 50: "above", 100: "above", 200: "above"},
        structure="higher_highs_higher_lows",
        nearest_swing_high=None,
        nearest_swing_low=None,
        bias_state="bullish_state",
    )
    return TickerReport(symbol=symbol, timeframes={"1D": state}, alignment="aligned_bullish", rr_ratio=2.0)


def test_nearby_snapshots_returns_closest_first(client):
    conn = get_connection()
    save_snapshot(conn, _report(), captured_at="2024-01-01T00:00:00+00:00")
    save_snapshot(conn, _report(), captured_at="2024-01-01T10:00:00+00:00")
    conn.close()

    resp = client.get("/api/snapshots/XRPUSDT/nearby", params={"around": "2024-01-01T09:00:00+00:00"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "XRPUSDT"
    assert len(body["snapshots"]) == 2
    assert body["snapshots"][0]["captured_at"] == "2024-01-01T10:00:00+00:00"

    summary = body["snapshots"][0]
    assert summary["alignment"] == "aligned_bullish"
    assert summary["rr_ratio"] == 2.0
    assert summary["daily_ma_stack"] == "bullish"
    assert summary["daily_rsi"] == 55.0


def test_nearby_snapshots_empty_when_no_history(client):
    resp = client.get("/api/snapshots/NOPEUSDT/nearby", params={"around": "2024-01-01T00:00:00+00:00"})
    assert resp.status_code == 200
    assert resp.json()["snapshots"] == []


def test_nearby_snapshots_rejects_bad_count(client):
    resp = client.get("/api/snapshots/XRPUSDT/nearby", params={"around": "2024-01-01T00:00:00+00:00", "count": 0})
    assert resp.status_code == 400
