from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import app
from confluence.data.fetch import fetch_ticker_from_provider
from confluence.data.providers.mock_provider import MockDataProvider
from confluence.screening.analysis import build_ticker_report
from confluence.snapshots.db import get_connection as get_snapshots_connection
from confluence.snapshots.store import save_snapshot


@pytest.fixture
def client(tmp_path):
    wallet_file = tmp_path / "wallet.db"
    snapshots_file = tmp_path / "snapshots.db"
    with patch("confluence.wallet.db.DB_FILE", wallet_file), \
         patch("confluence.snapshots.db.DB_FILE", snapshots_file):
        yield TestClient(app)


def test_scan_ingests_trades_into_needs_review(client):
    resp = client.post("/api/wallet/scan", json={"address": "0xabc123", "chain": "ethereum"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["data_source"] == "mock"
    assert body["trade_records_found"] == 3  # SAMPLE_SCENARIOS: 2 closed, 1 open
    assert body["new_trades_ingested"] == 3

    queue = client.get("/api/wallet/needs-review").json()
    assert len(queue) == 3
    assert all(t["review_status"] == "needs_review" for t in queue)
    tokens = {t["token_symbol"] for t in queue}
    assert tokens == {"XRP", "SOL", "ADA"}


def test_scan_is_idempotent_on_rescan(client):
    client.post("/api/wallet/scan", json={"address": "0xabc123"})
    second = client.post("/api/wallet/scan", json={"address": "0xabc123"}).json()
    assert second["new_trades_ingested"] == 0
    assert len(client.get("/api/wallet/needs-review").json()) == 3


def test_scan_rejects_blank_address(client):
    resp = client.post("/api/wallet/scan", json={"address": "   "})
    assert resp.status_code == 400


def test_annotate_moves_trade_from_needs_review_to_logged(client):
    client.post("/api/wallet/scan", json={"address": "0xabc123"})
    trade_id = client.get("/api/wallet/needs-review").json()[0]["id"]

    resp = client.post(f"/api/wallet/trades/{trade_id}/annotate", json={"reasoning": "confirmed breakout, sized normally"})
    assert resp.status_code == 200
    annotated = resp.json()
    assert annotated["review_status"] == "logged"
    assert annotated["reasoning"] == "confirmed breakout, sized normally"
    assert annotated["annotated_at"] is not None

    needs_review = client.get("/api/wallet/needs-review").json()
    logged = client.get("/api/wallet/logged").json()
    assert trade_id not in [t["id"] for t in needs_review]
    assert trade_id in [t["id"] for t in logged]


def test_annotate_with_linked_snapshot_computes_criteria_counts(client):
    # Seed a real snapshot for XRPUSDT so the annotation flow has
    # something genuine to score against (not synthetic test data).
    provider = MockDataProvider()
    enriched = fetch_ticker_from_provider(provider, "XRPUSDT", limit=300)
    report = build_ticker_report("XRPUSDT", enriched)
    snap_conn = get_snapshots_connection()
    snapshot = save_snapshot(snap_conn, report)
    snap_conn.close()

    client.post("/api/wallet/scan", json={"address": "0xabc123"})
    trades = client.get("/api/wallet/needs-review").json()
    xrp_trade = next(t for t in trades if t["token_symbol"] == "XRP")

    resp = client.post(
        f"/api/wallet/trades/{xrp_trade['id']}/annotate",
        json={"reasoning": "linked to the closest snapshot", "linked_snapshot_id": snapshot.id},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["linked_snapshot_id"] == snapshot.id
    assert body["criteria_total_count"] == 6
    assert 0 <= body["criteria_met_count"] <= 6


def test_annotate_rejects_blank_reasoning(client):
    client.post("/api/wallet/scan", json={"address": "0xabc123"})
    trade_id = client.get("/api/wallet/needs-review").json()[0]["id"]
    resp = client.post(f"/api/wallet/trades/{trade_id}/annotate", json={"reasoning": "  "})
    assert resp.status_code == 400


def test_annotate_unknown_trade_returns_404(client):
    resp = client.post("/api/wallet/trades/999/annotate", json={"reasoning": "reasoning"})
    assert resp.status_code == 404


def test_stats_reflect_only_logged_trades(client):
    empty_stats = client.get("/api/wallet/stats").json()
    assert empty_stats["logged_count"] == 0
    assert empty_stats["by_criteria"] == []

    client.post("/api/wallet/scan", json={"address": "0xabc123"})
    trades = client.get("/api/wallet/needs-review").json()
    for trade in trades:
        client.post(f"/api/wallet/trades/{trade['id']}/annotate", json={"reasoning": "reasoning"})

    stats = client.get("/api/wallet/stats").json()
    assert stats["logged_count"] == 3
    assert stats["closed_count"] == 2  # XRP + SOL closed, ADA still open
    assert stats["total_gas_fees"] > 0
