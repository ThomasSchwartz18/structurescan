"""Deterministic sample wallet transactions, for developing/testing the
wallet-scan feature before a real wallet/RPC endpoint is available.

Generates a handful of round-trip swaps (buy a token with USDT, later
sell it back) plus one still-open position, using the same token symbols
as Confluence's curated mock screener tickers (XRP, SOL, ADA, DOGE) so a
wallet trade's nearby criteria snapshots actually exist to link against
in a demo.
"""

from __future__ import annotations

import hashlib
import zlib
from datetime import datetime, timedelta, timezone

import numpy as np

from confluence.config import DEFAULT_WALLET_CHAIN
from confluence.wallet.providers.base import RawTransaction, WalletProvider

# token symbol -> a plausible current USDT price, loosely matched to the
# curated mock screener tickers' base prices (see confluence/data/
# providers/mock_provider.py) so wallet-trade prices look at-home next
# to the screener's own numbers in a demo.
TOKEN_BASE_PRICES = {
    "XRP": 2.85,
    "SOL": 142.00,
    "ADA": 0.74,
    "DOGE": 0.185,
}

# (token, days since entry, days since exit or None if still open)
SAMPLE_SCENARIOS = [
    ("XRP", 6, 4),
    ("SOL", 5, 2),
    ("ADA", 3, None),
]

NATIVE_CURRENCY = "ETH"


def _seed(address: str) -> int:
    return zlib.crc32(f"confluence-wallet-mock:{address.lower()}".encode()) & 0xFFFFFFFF


def _fake_tx_hash(address: str, token: str, kind: str) -> str:
    digest = hashlib.sha256(f"{address.lower()}:{token}:{kind}".encode()).hexdigest()
    return f"0x{digest}"


def generate_transactions(
    address: str,
    chain: str,
    limit: int,
    *,
    now: datetime,
) -> list[RawTransaction]:
    """Pure generator (no wall-clock access beyond the given `now`), kept
    separate from MockWalletProvider so tests can call it with a fixed
    `now` for deterministic assertions — the provider itself anchors to
    the real current time on every call, same as MockDataProvider does
    for OHLCV, so a scan's transactions stay recent as real time passes."""
    rng = np.random.default_rng(_seed(address))
    transactions: list[RawTransaction] = []

    for token, entry_days_ago, exit_days_ago in SAMPLE_SCENARIOS:
        base_price = TOKEN_BASE_PRICES[token]
        entry_price = base_price * float(rng.uniform(0.9, 1.1))
        token_amount = float(rng.uniform(50, 500))
        usdt_spent = entry_price * token_amount

        entry_time = now - timedelta(days=entry_days_ago, hours=float(rng.uniform(0, 23)))
        transactions.append(
            RawTransaction(
                tx_hash=_fake_tx_hash(address, token, "entry"),
                timestamp=entry_time.isoformat(),
                chain=chain,
                token_in_symbol="USDT",
                token_in_amount=usdt_spent,
                token_out_symbol=token,
                token_out_amount=token_amount,
                gas_fee_native=float(rng.uniform(0.001, 0.01)),
                native_currency=NATIVE_CURRENCY,
            )
        )

        if exit_days_ago is not None:
            exit_price = base_price * float(rng.uniform(0.85, 1.3))
            usdt_received = exit_price * token_amount
            exit_time = now - timedelta(days=exit_days_ago, hours=float(rng.uniform(0, 23)))
            transactions.append(
                RawTransaction(
                    tx_hash=_fake_tx_hash(address, token, "exit"),
                    timestamp=exit_time.isoformat(),
                    chain=chain,
                    token_in_symbol=token,
                    token_in_amount=token_amount,
                    token_out_symbol="USDT",
                    token_out_amount=usdt_received,
                    gas_fee_native=float(rng.uniform(0.001, 0.01)),
                    native_currency=NATIVE_CURRENCY,
                )
            )

    transactions.sort(key=lambda t: t.timestamp)
    return transactions[:limit]


class MockWalletProvider(WalletProvider):
    def get_transactions(
        self, address: str, chain: str = DEFAULT_WALLET_CHAIN, limit: int = 50
    ) -> list[RawTransaction]:
        return generate_transactions(address, chain, limit, now=datetime.now(timezone.utc))
