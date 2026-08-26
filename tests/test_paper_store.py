import pytest

from confluence.config import PAPER_STARTING_BALANCE
from confluence.paper.db import get_connection
from confluence.paper.store import (
    PaperTradingError,
    close_trade,
    compute_pnl,
    compute_stats,
    get_starting_balance,
    get_trade,
    list_closed_trades,
    list_open_trades,
    open_trade,
)


@pytest.fixture
def conn(tmp_path):
    connection = get_connection(tmp_path / "test.db")
    yield connection
    connection.close()


def _open(conn, **overrides):
    params = dict(
        symbol="xrpusdt",
        direction="long",
        entry_price=2.85,
        size=100.0,
        stop_loss=2.70,
        take_profit=3.10,
        reasoning="daily RSI extended but lower timeframes aligned bullish",
    )
    params.update(overrides)
    return open_trade(conn, **params)


def test_get_connection_initializes_account_row(conn):
    assert get_starting_balance(conn) == PAPER_STARTING_BALANCE


def test_open_trade_persists_and_uppercases_symbol(conn):
    trade = _open(conn)
    assert trade.symbol == "XRPUSDT"
    assert trade.status == "open"
    assert trade.id is not None
    assert trade.exit_price is None
    assert trade.realized_pnl is None

    fetched = get_trade(conn, trade.id)
    assert fetched == trade


def test_open_trade_rejects_invalid_direction(conn):
    with pytest.raises(PaperTradingError):
        _open(conn, direction="sideways")


@pytest.mark.parametrize("field", ["entry_price", "size"])
def test_open_trade_rejects_non_positive_numbers(conn, field):
    with pytest.raises(PaperTradingError):
        _open(conn, **{field: 0})
    with pytest.raises(PaperTradingError):
        _open(conn, **{field: -5})


def test_open_trade_rejects_blank_reasoning(conn):
    with pytest.raises(PaperTradingError):
        _open(conn, reasoning="   ")


def test_open_trade_allows_null_stop_loss_and_take_profit(conn):
    trade = _open(conn, stop_loss=None, take_profit=None)
    assert trade.stop_loss is None
    assert trade.take_profit is None


def test_compute_pnl_long_profit_and_loss(conn):
    trade = _open(conn, direction="long", entry_price=100.0, size=10.0)
    assert compute_pnl(trade, 110.0) == pytest.approx(100.0)   # +$10/unit * 10
    assert compute_pnl(trade, 90.0) == pytest.approx(-100.0)


def test_compute_pnl_short_profit_and_loss(conn):
    trade = _open(conn, direction="short", entry_price=100.0, size=10.0)
    assert compute_pnl(trade, 90.0) == pytest.approx(100.0)    # price fell, short profits
    assert compute_pnl(trade, 110.0) == pytest.approx(-100.0)


def test_close_trade_records_exit_and_realized_pnl(conn):
    trade = _open(conn, direction="long", entry_price=100.0, size=5.0)
    closed = close_trade(conn, trade.id, 120.0)
    assert closed.status == "closed"
    assert closed.exit_price == 120.0
    assert closed.realized_pnl == pytest.approx(100.0)
    assert closed.closed_at is not None


def test_close_trade_rejects_already_closed(conn):
    trade = _open(conn)
    close_trade(conn, trade.id, 3.0)
    with pytest.raises(PaperTradingError):
        close_trade(conn, trade.id, 3.1)


def test_close_trade_rejects_unknown_id(conn):
    with pytest.raises(PaperTradingError):
        close_trade(conn, 999, 3.0)


def test_close_trade_rejects_non_positive_exit_price(conn):
    trade = _open(conn)
    with pytest.raises(PaperTradingError):
        close_trade(conn, trade.id, 0)


def test_list_open_and_closed_trades_partition_correctly(conn):
    a = _open(conn, symbol="AAA")
    b = _open(conn, symbol="BBB")
    close_trade(conn, a.id, 3.0)

    open_ids = {t.id for t in list_open_trades(conn)}
    closed_ids = {t.id for t in list_closed_trades(conn)}
    assert open_ids == {b.id}
    assert closed_ids == {a.id}


def test_compute_stats_with_no_closed_trades(conn):
    stats = compute_stats(conn)
    assert stats.starting_balance == PAPER_STARTING_BALANCE
    assert stats.realized_pnl_total == 0.0
    assert stats.equity == PAPER_STARTING_BALANCE
    assert stats.closed_count == 0
    assert stats.win_rate is None
    assert stats.avg_win is None
    assert stats.avg_loss is None


def test_compute_stats_mixed_wins_and_losses(conn):
    t1 = _open(conn, symbol="AAA", direction="long", entry_price=100.0, size=1.0)
    t2 = _open(conn, symbol="BBB", direction="long", entry_price=100.0, size=1.0)
    t3 = _open(conn, symbol="CCC", direction="long", entry_price=100.0, size=1.0)
    close_trade(conn, t1.id, 110.0)  # +10
    close_trade(conn, t2.id, 90.0)   # -10
    close_trade(conn, t3.id, 120.0)  # +20

    stats = compute_stats(conn)
    assert stats.closed_count == 3
    assert stats.win_count == 2
    assert stats.loss_count == 1
    assert stats.win_rate == pytest.approx(2 / 3)
    assert stats.avg_win == pytest.approx(15.0)
    assert stats.avg_loss == pytest.approx(-10.0)
    assert stats.realized_pnl_total == pytest.approx(20.0)
    assert stats.equity == pytest.approx(PAPER_STARTING_BALANCE + 20.0)


def test_compute_stats_breakeven_trade_counts_as_neither_win_nor_loss(conn):
    trade = _open(conn, direction="long", entry_price=100.0, size=1.0)
    close_trade(conn, trade.id, 100.0)  # exactly flat

    stats = compute_stats(conn)
    assert stats.closed_count == 1
    assert stats.win_count == 0
    assert stats.loss_count == 0
    assert stats.win_rate == 0.0


def test_open_trades_do_not_affect_stats_until_closed(conn):
    _open(conn)
    stats = compute_stats(conn)
    assert stats.closed_count == 0
    assert stats.equity == PAPER_STARTING_BALANCE
