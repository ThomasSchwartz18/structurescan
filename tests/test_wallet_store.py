import pytest

from confluence.wallet.db import get_connection
from confluence.wallet.normalize import WalletTradeRecord
from confluence.wallet.store import (
    WalletJournalError,
    annotate_trade,
    compute_wallet_stats,
    get_wallet_trade,
    ingest_trade_records,
    list_logged,
    list_needs_review,
)


@pytest.fixture
def conn(tmp_path):
    connection = get_connection(tmp_path / "wallet_test.db")
    yield connection
    connection.close()


def _record(**overrides):
    defaults = dict(
        token_symbol="XRP",
        direction="long",
        entry_price=2.85,
        entry_timestamp="2024-01-01T00:00:00+00:00",
        entry_tx_hash="0xentry1",
        exit_price=3.10,
        exit_timestamp="2024-01-05T00:00:00+00:00",
        exit_tx_hash="0xexit1",
        size=100.0,
        realized_pnl=25.0,
        gas_fee_total=0.01,
        status="closed",
    )
    defaults.update(overrides)
    return WalletTradeRecord(**defaults)


def test_ingest_new_records_land_in_needs_review(conn):
    inserted = ingest_trade_records(conn, [_record()])
    assert inserted == 1

    queue = list_needs_review(conn)
    assert len(queue) == 1
    assert queue[0].token_symbol == "XRP"
    assert queue[0].review_status == "needs_review"
    assert queue[0].realized_pnl == pytest.approx(25.0)


def test_ingest_is_idempotent_on_entry_tx_hash(conn):
    ingest_trade_records(conn, [_record()])
    inserted_again = ingest_trade_records(conn, [_record()])  # same entry_tx_hash
    assert inserted_again == 0
    assert len(list_needs_review(conn)) == 1


def test_ingest_open_position_has_no_exit_or_pnl(conn):
    open_record = _record(
        entry_tx_hash="0xopen",
        exit_price=None,
        exit_timestamp=None,
        exit_tx_hash=None,
        realized_pnl=None,
        status="open",
    )
    ingest_trade_records(conn, [open_record])
    trade = list_needs_review(conn)[0]
    assert trade.position_status == "open"
    assert trade.exit_price is None
    assert trade.realized_pnl is None


def test_annotate_trade_moves_it_to_logged(conn):
    ingest_trade_records(conn, [_record()])
    trade_id = list_needs_review(conn)[0].id

    annotated = annotate_trade(conn, trade_id, "entered on a 4H pullback", criteria_met_count=5, criteria_total_count=6)
    assert annotated.review_status == "logged"
    assert annotated.reasoning == "entered on a 4H pullback"
    assert annotated.criteria_met_count == 5
    assert annotated.annotated_at is not None

    assert list_needs_review(conn) == []
    assert len(list_logged(conn)) == 1


def test_annotate_trade_rejects_blank_reasoning(conn):
    ingest_trade_records(conn, [_record()])
    trade_id = list_needs_review(conn)[0].id
    with pytest.raises(WalletJournalError):
        annotate_trade(conn, trade_id, "   ")


def test_annotate_unknown_trade_raises(conn):
    with pytest.raises(WalletJournalError):
        annotate_trade(conn, 999, "reasoning")


def test_get_wallet_trade_unknown_raises(conn):
    with pytest.raises(WalletJournalError):
        get_wallet_trade(conn, 999)


def test_stats_only_reflect_logged_closed_trades(conn):
    ingest_trade_records(conn, [_record(entry_tx_hash="0xa")])
    stats = compute_wallet_stats(conn)
    assert stats.logged_count == 0
    assert stats.closed_count == 0
    assert stats.total_realized_pnl == 0.0

    trade_id = list_needs_review(conn)[0].id
    annotate_trade(conn, trade_id, "reasoning", criteria_met_count=4, criteria_total_count=6)

    stats = compute_wallet_stats(conn)
    assert stats.logged_count == 1
    assert stats.closed_count == 1
    assert stats.total_realized_pnl == pytest.approx(25.0)
    assert stats.win_count == 1
    assert stats.win_rate == pytest.approx(1.0)


def test_stats_include_gas_fees_for_open_and_closed_logged_trades(conn):
    ingest_trade_records(conn, [
        _record(entry_tx_hash="0xa", gas_fee_total=0.01),
        _record(
            entry_tx_hash="0xb", exit_price=None, exit_timestamp=None, exit_tx_hash=None,
            realized_pnl=None, status="open", gas_fee_total=0.02,
        ),
    ])
    for trade in list_needs_review(conn):
        annotate_trade(conn, trade.id, "reasoning")

    stats = compute_wallet_stats(conn)
    assert stats.total_gas_fees == pytest.approx(0.03)


def test_stats_breakdown_by_criteria_met(conn):
    ingest_trade_records(conn, [
        _record(entry_tx_hash="0xa", realized_pnl=50.0),   # win, 6/6
        _record(entry_tx_hash="0xb", realized_pnl=30.0),   # win, 6/6
        _record(entry_tx_hash="0xc", realized_pnl=-20.0),  # loss, 2/6
    ])
    trades = list_needs_review(conn)
    annotate_trade(conn, trades[0].id, "r1", criteria_met_count=6, criteria_total_count=6)
    annotate_trade(conn, trades[1].id, "r2", criteria_met_count=6, criteria_total_count=6)
    annotate_trade(conn, trades[2].id, "r3", criteria_met_count=2, criteria_total_count=6)

    stats = compute_wallet_stats(conn)
    assert len(stats.by_criteria) == 2

    high_bucket = next(b for b in stats.by_criteria if b.met_count == 6)
    low_bucket = next(b for b in stats.by_criteria if b.met_count == 2)

    assert high_bucket.trade_count == 2
    assert high_bucket.win_count == 2
    assert high_bucket.win_rate == pytest.approx(1.0)
    assert high_bucket.total_pnl == pytest.approx(80.0)

    assert low_bucket.trade_count == 1
    assert low_bucket.win_count == 0
    assert low_bucket.win_rate == pytest.approx(0.0)
    assert low_bucket.total_pnl == pytest.approx(-20.0)


def test_stats_excludes_trades_without_a_linked_criteria_count_from_breakdown(conn):
    ingest_trade_records(conn, [_record(entry_tx_hash="0xa")])
    trade_id = list_needs_review(conn)[0].id
    annotate_trade(conn, trade_id, "reasoning")  # no criteria_met_count given

    stats = compute_wallet_stats(conn)
    assert stats.by_criteria == []
    assert stats.closed_count == 1  # still counted in the overall stats
