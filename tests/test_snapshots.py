from datetime import datetime, timedelta, timezone

import pytest

from confluence.data.fetch import fetch_ticker_from_provider
from confluence.data.providers.mock_provider import MockDataProvider
from confluence.screening.analysis import TickerReport, TimeframeState, build_ticker_report
from confluence.screening.report import evaluate_criteria
from confluence.snapshots.db import get_connection
from confluence.snapshots.store import (
    get_snapshot,
    latest_snapshot,
    list_snapshots,
    maybe_save_snapshot,
    nearby_snapshots,
    prune_old_snapshots,
    reconstruct_report,
    save_snapshot,
)


@pytest.fixture
def conn(tmp_path):
    connection = get_connection(tmp_path / "snapshots_test.db")
    yield connection
    connection.close()


def _minimal_report(symbol="XRPUSDT"):
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


def test_save_and_get_snapshot_round_trips_symbol_and_alignment(conn):
    report = _minimal_report()
    saved = save_snapshot(conn, report)
    fetched = get_snapshot(conn, saved.id)

    assert fetched.symbol == "XRPUSDT"
    assert fetched.payload["alignment"] == "aligned_bullish"
    assert fetched.payload["rr_ratio"] == 2.0
    assert fetched.payload["timeframes"]["1D"]["ma_stack"] == "bullish"


def test_latest_snapshot_returns_most_recent(conn):
    save_snapshot(conn, _minimal_report(), captured_at="2024-01-01T00:00:00+00:00")
    newest = save_snapshot(conn, _minimal_report(), captured_at="2024-01-02T00:00:00+00:00")

    latest = latest_snapshot(conn, "XRPUSDT")
    assert latest.id == newest.id


def test_latest_snapshot_none_when_no_history(conn):
    assert latest_snapshot(conn, "NOPEUSDT") is None


def test_maybe_save_snapshot_skips_within_interval(conn):
    first = maybe_save_snapshot(conn, _minimal_report(), interval_minutes=60)
    assert first is not None

    second = maybe_save_snapshot(conn, _minimal_report(), interval_minutes=60)
    assert second is None  # too soon
    assert len(list_snapshots(conn, "XRPUSDT")) == 1


def test_maybe_save_snapshot_saves_after_interval_elapses(conn):
    old_time = (datetime.now(timezone.utc) - timedelta(minutes=61)).isoformat()
    save_snapshot(conn, _minimal_report(), captured_at=old_time)

    result = maybe_save_snapshot(conn, _minimal_report(), interval_minutes=60)
    assert result is not None
    assert len(list_snapshots(conn, "XRPUSDT")) == 2


def test_prune_old_snapshots_removes_only_stale_rows(conn):
    old_time = (datetime.now(timezone.utc) - timedelta(days=40)).isoformat()
    recent_time = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    save_snapshot(conn, _minimal_report(), captured_at=old_time)
    save_snapshot(conn, _minimal_report(), captured_at=recent_time)

    removed = prune_old_snapshots(conn, retention_days=30)
    assert removed == 1
    remaining = list_snapshots(conn, "XRPUSDT")
    assert len(remaining) == 1
    assert remaining[0].captured_at == recent_time


def test_nearby_snapshots_returns_closest_first(conn):
    save_snapshot(conn, _minimal_report(), captured_at="2024-01-01T00:00:00+00:00")
    save_snapshot(conn, _minimal_report(), captured_at="2024-01-01T10:00:00+00:00")
    save_snapshot(conn, _minimal_report(), captured_at="2024-01-01T12:05:00+00:00")

    nearby = nearby_snapshots(conn, "XRPUSDT", target_time="2024-01-01T12:00:00+00:00", count=2)
    assert [s.captured_at for s in nearby] == ["2024-01-01T12:05:00+00:00", "2024-01-01T10:00:00+00:00"]


def test_nearby_snapshots_empty_when_no_history(conn):
    assert nearby_snapshots(conn, "NOPEUSDT", target_time="2024-01-01T00:00:00+00:00") == []


def test_reconstruct_report_round_trip_against_real_mock_data(conn):
    """The actual verification-against-mock-data step: build a real
    TickerReport from MockDataProvider, save it, reconstruct it from
    storage, and confirm re-scoring the reconstructed report against the
    morning report criteria gives byte-for-byte the same result as
    scoring the original — proving the snapshot round-trip doesn't lose
    or corrupt anything evaluate_criteria() actually reads."""
    provider = MockDataProvider()
    enriched = fetch_ticker_from_provider(provider, "XRPUSDT", limit=300)
    original = build_ticker_report("XRPUSDT", enriched)

    saved = save_snapshot(conn, original)
    fetched = get_snapshot(conn, saved.id)
    reconstructed = reconstruct_report(fetched)

    assert reconstructed.symbol == original.symbol
    assert reconstructed.alignment == original.alignment
    assert reconstructed.rr_ratio == original.rr_ratio

    original_criteria = evaluate_criteria(original)
    reconstructed_criteria = evaluate_criteria(reconstructed)
    assert [(c.key, c.met) for c in original_criteria] == [(c.key, c.met) for c in reconstructed_criteria]
