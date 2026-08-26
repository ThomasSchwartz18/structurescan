from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from confluence.api.app import app
from confluence.config import PAPER_STARTING_BALANCE


@pytest.fixture
def client(tmp_path):
    state_file = tmp_path / "tickers.local.json"
    db_file = tmp_path / "paper_trades.db"
    with patch("confluence.watchlist.STATE_FILE", state_file), \
         patch("confluence.paper.db.DB_FILE", db_file):
        yield TestClient(app)


def _open_payload(**overrides):
    payload = dict(
        symbol="xrpusdt",
        direction="long",
        entry_price=2.85,
        size=100.0,
        stop_loss=2.70,
        take_profit=3.10,
        reasoning="daily RSI extended but 4H/1H/15min aligned bullish, entering on pullback",
    )
    payload.update(overrides)
    return payload


def test_open_trade_then_appears_in_open_positions_with_live_pnl(client):
    resp = client.post("/api/paper/trades", json=_open_payload())
    assert resp.status_code == 200
    trade = resp.json()
    assert trade["symbol"] == "XRPUSDT"
    assert trade["status"] == "open"

    open_resp = client.get("/api/paper/trades/open")
    assert open_resp.status_code == 200
    rows = open_resp.json()
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == trade["id"]
    assert row["current_price"] is not None
    assert row["price_error"] is None
    # XRPUSDT is a curated mock ticker with a real, non-degenerate price series.
    assert row["unrealized_pnl"] == pytest.approx(
        (row["current_price"] - row["entry_price"]) * row["size"]
    )


def test_open_trade_rejects_missing_reasoning(client):
    resp = client.post("/api/paper/trades", json=_open_payload(reasoning="  "))
    assert resp.status_code == 400


def test_open_trade_rejects_invalid_direction(client):
    resp = client.post("/api/paper/trades", json=_open_payload(direction="sideways"))
    assert resp.status_code == 422  # pydantic Literal validation


def test_open_trade_rejects_non_positive_size(client):
    resp = client.post("/api/paper/trades", json=_open_payload(size=0))
    assert resp.status_code == 400


def test_close_position_uses_live_price_and_moves_to_journal(client):
    open_resp = client.post("/api/paper/trades", json=_open_payload())
    trade_id = open_resp.json()["id"]

    price_resp = client.get("/api/paper/trades/open")
    expected_price = price_resp.json()[0]["current_price"]

    close_resp = client.post(f"/api/paper/trades/{trade_id}/close")
    assert close_resp.status_code == 200
    closed = close_resp.json()
    assert closed["status"] == "closed"
    assert closed["exit_price"] == pytest.approx(expected_price)
    assert closed["realized_pnl"] == pytest.approx(
        (expected_price - closed["entry_price"]) * closed["size"]
    )

    assert client.get("/api/paper/trades/open").json() == []
    journal = client.get("/api/paper/trades/closed").json()
    assert len(journal) == 1
    assert journal[0]["id"] == trade_id
    assert journal[0]["reasoning"] == _open_payload()["reasoning"]


def test_close_unknown_trade_returns_404(client):
    resp = client.post("/api/paper/trades/999/close")
    assert resp.status_code == 404


def test_close_already_closed_trade_returns_400(client):
    trade_id = client.post("/api/paper/trades", json=_open_payload()).json()["id"]
    client.post(f"/api/paper/trades/{trade_id}/close")
    resp = client.post(f"/api/paper/trades/{trade_id}/close")
    assert resp.status_code == 400


def test_stats_reflect_closed_trades_only(client):
    empty_stats = client.get("/api/paper/stats").json()
    assert empty_stats["starting_balance"] == PAPER_STARTING_BALANCE
    assert empty_stats["closed_count"] == 0
    assert empty_stats["equity"] == PAPER_STARTING_BALANCE

    trade_id = client.post("/api/paper/trades", json=_open_payload()).json()["id"]
    mid_stats = client.get("/api/paper/stats").json()
    assert mid_stats["closed_count"] == 0  # still open, doesn't count yet

    client.post(f"/api/paper/trades/{trade_id}/close")
    final_stats = client.get("/api/paper/stats").json()
    assert final_stats["closed_count"] == 1
    assert final_stats["equity"] == pytest.approx(
        PAPER_STARTING_BALANCE + final_stats["realized_pnl_total"]
    )


def test_short_trade_pnl_direction(client):
    trade_id = client.post(
        "/api/paper/trades", json=_open_payload(direction="short", entry_price=100000.0, size=1.0)
    ).json()["id"]
    closed = client.post(f"/api/paper/trades/{trade_id}/close").json()
    # short: profits when price falls below entry, loses when price rises above it.
    if closed["exit_price"] < 100000.0:
        assert closed["realized_pnl"] > 0
    elif closed["exit_price"] > 100000.0:
        assert closed["realized_pnl"] < 0
    else:
        assert closed["realized_pnl"] == 0
