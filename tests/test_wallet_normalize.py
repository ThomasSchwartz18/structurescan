import pytest

from confluence.wallet.normalize import normalize_transactions
from confluence.wallet.providers.base import RawTransaction
from confluence.wallet.providers.mock_provider import MockWalletProvider

BASE = {"USDT", "USDC"}


def _tx(token_in, amount_in, token_out, amount_out, ts, gas=0.005, tx_hash=None):
    return RawTransaction(
        tx_hash=tx_hash or f"0x{ts}{token_in}{token_out}",
        timestamp=ts,
        chain="ethereum",
        token_in_symbol=token_in,
        token_in_amount=amount_in,
        token_out_symbol=token_out,
        token_out_amount=amount_out,
        gas_fee_native=gas,
        native_currency="ETH",
    )


def test_simple_entry_and_exit_pair_into_closed_record():
    entry = _tx("USDT", 285.0, "XRP", 100.0, "2024-01-01T00:00:00+00:00", gas=0.002, tx_hash="0xentry")
    exit_ = _tx("XRP", 100.0, "USDT", 310.0, "2024-01-05T00:00:00+00:00", gas=0.003, tx_hash="0xexit")

    records = normalize_transactions([entry, exit_], base_currencies=BASE)
    assert len(records) == 1
    record = records[0]

    assert record.token_symbol == "XRP"
    assert record.direction == "long"
    assert record.status == "closed"
    assert record.size == pytest.approx(100.0)
    assert record.entry_price == pytest.approx(2.85)
    assert record.exit_price == pytest.approx(3.10)
    assert record.realized_pnl == pytest.approx(25.0)  # 310 - 285
    assert record.gas_fee_total == pytest.approx(0.005)
    assert record.entry_tx_hash == "0xentry"
    assert record.exit_tx_hash == "0xexit"


def test_entry_without_exit_is_an_open_record():
    entry = _tx("USDT", 285.0, "XRP", 100.0, "2024-01-01T00:00:00+00:00", tx_hash="0xentry")

    records = normalize_transactions([entry], base_currencies=BASE)
    assert len(records) == 1
    record = records[0]

    assert record.status == "open"
    assert record.exit_price is None
    assert record.exit_timestamp is None
    assert record.realized_pnl is None
    assert record.gas_fee_total == pytest.approx(entry.gas_fee_native)


def test_losing_trade_has_negative_realized_pnl():
    entry = _tx("USDT", 300.0, "XRP", 100.0, "2024-01-01T00:00:00+00:00", tx_hash="0xentry")
    exit_ = _tx("XRP", 100.0, "USDT", 250.0, "2024-01-02T00:00:00+00:00", tx_hash="0xexit")

    records = normalize_transactions([entry, exit_], base_currencies=BASE)
    assert records[0].realized_pnl == pytest.approx(-50.0)


def test_fifo_pairs_oldest_entry_with_first_exit():
    entry1 = _tx("USDT", 100.0, "XRP", 50.0, "2024-01-01T00:00:00+00:00", tx_hash="entry1")
    entry2 = _tx("USDT", 110.0, "XRP", 50.0, "2024-01-02T00:00:00+00:00", tx_hash="entry2")
    exit1 = _tx("XRP", 50.0, "USDT", 120.0, "2024-01-03T00:00:00+00:00", tx_hash="exit1")
    exit2 = _tx("XRP", 50.0, "USDT", 130.0, "2024-01-04T00:00:00+00:00", tx_hash="exit2")

    records = normalize_transactions([entry2, exit2, entry1, exit1], base_currencies=BASE)  # shuffled input
    assert len(records) == 2

    first, second = records  # sorted by entry_timestamp
    assert first.entry_tx_hash == "entry1"
    assert first.exit_tx_hash == "exit1"
    assert second.entry_tx_hash == "entry2"
    assert second.exit_tx_hash == "exit2"


def test_exit_with_no_matching_entry_is_skipped():
    orphan_exit = _tx("XRP", 100.0, "USDT", 300.0, "2024-01-01T00:00:00+00:00", tx_hash="orphan")
    records = normalize_transactions([orphan_exit], base_currencies=BASE)
    assert records == []


def test_token_to_token_swap_not_involving_base_currency_is_ignored():
    swap = _tx("XRP", 100.0, "SOL", 2.0, "2024-01-01T00:00:00+00:00")
    records = normalize_transactions([swap], base_currencies=BASE)
    assert records == []


def test_different_tokens_tracked_independently():
    xrp_entry = _tx("USDT", 285.0, "XRP", 100.0, "2024-01-01T00:00:00+00:00", tx_hash="xrp_entry")
    sol_entry = _tx("USDT", 1420.0, "SOL", 10.0, "2024-01-01T01:00:00+00:00", tx_hash="sol_entry")
    xrp_exit = _tx("XRP", 100.0, "USDT", 300.0, "2024-01-02T00:00:00+00:00", tx_hash="xrp_exit")

    records = normalize_transactions([xrp_entry, sol_entry, xrp_exit], base_currencies=BASE)
    assert len(records) == 2

    xrp_record = next(r for r in records if r.token_symbol == "XRP")
    sol_record = next(r for r in records if r.token_symbol == "SOL")
    assert xrp_record.status == "closed"
    assert sol_record.status == "open"


def test_normalize_against_real_mock_wallet_provider_output():
    """The actual verify-against-mock-data step: run the real
    MockWalletProvider's output through normalization and confirm it
    produces the expected shape (2 closed round trips, 1 still open,
    matching MockWalletProvider's SAMPLE_SCENARIOS)."""
    provider = MockWalletProvider()
    transactions = provider.get_transactions("0xabc123")
    records = normalize_transactions(transactions)

    assert len(records) == 3
    by_token = {r.token_symbol: r for r in records}
    assert by_token["XRP"].status == "closed"
    assert by_token["SOL"].status == "closed"
    assert by_token["ADA"].status == "open"

    for record in records:
        assert record.entry_price > 0
        assert record.size > 0
        assert record.gas_fee_total > 0
        if record.status == "closed":
            assert record.exit_price > 0
            assert record.realized_pnl is not None
