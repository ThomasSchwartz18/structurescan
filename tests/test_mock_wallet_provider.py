from datetime import datetime, timezone

import pytest

from confluence.wallet.providers.mock_provider import MockWalletProvider, generate_transactions

FIXED_NOW = datetime(2024, 6, 15, 12, 0, 0, tzinfo=timezone.utc)


def test_generate_transactions_deterministic_for_fixed_instant():
    a = generate_transactions("0xabc123", "ethereum", 50, now=FIXED_NOW)
    b = generate_transactions("0xabc123", "ethereum", 50, now=FIXED_NOW)
    assert a == b


def test_get_transactions_reflects_current_wall_clock_time():
    # The provider itself anchors to real "now" on each call (so a scan
    # stays recent as time passes) — confirm timestamps land in the
    # expected recent-past window rather than testing byte-for-byte
    # equality across two different real instants, which the provider
    # was never meant to guarantee.
    provider = MockWalletProvider()
    txs = provider.get_transactions("0xabc123")
    now = datetime.now(timezone.utc)
    for tx in txs:
        tx_time = datetime.fromisoformat(tx.timestamp)
        assert tx_time <= now
        assert (now - tx_time).days <= 7


def test_get_transactions_differs_for_different_addresses():
    provider = MockWalletProvider()
    a = provider.get_transactions("0xabc123")
    b = provider.get_transactions("0xdef456")
    assert a != b


def test_get_transactions_sorted_chronologically():
    provider = MockWalletProvider()
    txs = provider.get_transactions("0xabc123")
    timestamps = [t.timestamp for t in txs]
    assert timestamps == sorted(timestamps)


def test_get_transactions_includes_both_closed_and_open_scenarios():
    # SAMPLE_SCENARIOS has 3 tokens: 2 with a matching exit (closed),
    # 1 with entry only (still open) -> 2*2 + 1 = 5 transactions total.
    provider = MockWalletProvider()
    txs = provider.get_transactions("0xabc123")
    assert len(txs) == 5


def test_get_transactions_respects_limit():
    provider = MockWalletProvider()
    txs = provider.get_transactions("0xabc123", limit=2)
    assert len(txs) == 2


def test_transactions_have_plausible_positive_amounts_and_fees():
    provider = MockWalletProvider()
    for tx in provider.get_transactions("0xabc123"):
        assert tx.token_in_amount > 0
        assert tx.token_out_amount > 0
        assert tx.gas_fee_native > 0
        assert tx.tx_hash.startswith("0x")
        assert len(tx.tx_hash) == 66  # "0x" + 64 hex chars, like a real tx hash


def test_entry_and_exit_are_distinguishable_by_token_direction():
    provider = MockWalletProvider()
    txs = provider.get_transactions("0xabc123")
    xrp_txs = [t for t in txs if "XRP" in (t.token_in_symbol, t.token_out_symbol)]
    assert len(xrp_txs) == 2
    entry = next(t for t in xrp_txs if t.token_out_symbol == "XRP")
    exit_ = next(t for t in xrp_txs if t.token_in_symbol == "XRP")
    assert entry.token_in_symbol == "USDT"
    assert exit_.token_out_symbol == "USDT"
    assert entry.timestamp < exit_.timestamp
