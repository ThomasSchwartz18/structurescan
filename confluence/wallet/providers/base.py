"""Wallet transaction history abstraction — mirrors confluence.data.
providers.DataProvider: everything downstream (normalization, the
Needs Review queue) talks only to this interface, never to a concrete
provider.

Read-only by construction: there is no method here for signing,
broadcasting, or otherwise executing a transaction, and there never
should be. A WalletProvider only ever reads history for a public
address; it has no way to move funds even in principle.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from confluence.config import DEFAULT_WALLET_CHAIN


class WalletProviderError(RuntimeError):
    """Raised when a provider can't return transaction history for an
    address/chain."""


@dataclass
class RawTransaction:
    """One on-chain swap, as a wallet/explorer API would report it —
    before any interpretation of which side is the "traded" token vs.
    the "base" currency (see confluence/wallet/normalize.py for that)."""

    tx_hash: str
    timestamp: str  # ISO 8601
    chain: str
    token_in_symbol: str
    token_in_amount: float
    token_out_symbol: str
    token_out_amount: float
    gas_fee_native: float
    native_currency: str  # e.g. "ETH" — the chain's gas currency, not necessarily either swapped token


class WalletProvider(ABC):
    @abstractmethod
    def get_transactions(
        self, address: str, chain: str = DEFAULT_WALLET_CHAIN, limit: int = 50
    ) -> list[RawTransaction]:
        """Return up to `limit` swap transactions for `address` on
        `chain`, oldest first. `address` is always a public wallet
        address — nothing in this interface accepts or needs a private
        key or seed phrase."""
