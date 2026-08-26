"""Turn raw wallet swap transactions into normalized trade records.

A swap is classified by which side is a "base"/quote currency
(WALLET_BASE_CURRENCIES): swapping a base currency for something else is
an entry into that token; swapping a tracked token back into a base
currency is an exit. Entries and exits for the same token are paired
FIFO (oldest unmatched entry pairs with the next exit) — same-day partial
fills or lot-splitting aren't modeled in v1; each exit is assumed to
close exactly the size of the entry it's paired with. A future real
implementation should refine this if a wallet's actual trading pattern
needs it.

All amounts are direction-agnostic here on purpose: on a spot wallet
there is no borrowing, so every trade this can ever produce is a "long"
in the paper-trading sense (buy low, sell high) — there's no way to
express a short from swap history alone.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional

from confluence.config import WALLET_BASE_CURRENCIES
from confluence.wallet.providers.base import RawTransaction


@dataclass
class WalletTradeRecord:
    token_symbol: str
    direction: str  # always "long" for v1 — see module docstring
    entry_price: float
    entry_timestamp: str
    entry_tx_hash: str
    exit_price: Optional[float]
    exit_timestamp: Optional[str]
    exit_tx_hash: Optional[str]
    size: float
    realized_pnl: Optional[float]  # gross, in the base currency; excludes gas
    gas_fee_total: float
    status: str  # "open" | "closed"


def _is_entry(tx: RawTransaction, base_currencies: set[str]) -> bool:
    return tx.token_in_symbol in base_currencies and tx.token_out_symbol not in base_currencies


def _is_exit(tx: RawTransaction, base_currencies: set[str]) -> bool:
    return tx.token_out_symbol in base_currencies and tx.token_in_symbol not in base_currencies


def _closed_record(entry_tx: RawTransaction, exit_tx: RawTransaction) -> WalletTradeRecord:
    entry_price = entry_tx.token_in_amount / entry_tx.token_out_amount
    exit_price = exit_tx.token_out_amount / exit_tx.token_in_amount
    return WalletTradeRecord(
        token_symbol=entry_tx.token_out_symbol,
        direction="long",
        entry_price=entry_price,
        entry_timestamp=entry_tx.timestamp,
        entry_tx_hash=entry_tx.tx_hash,
        exit_price=exit_price,
        exit_timestamp=exit_tx.timestamp,
        exit_tx_hash=exit_tx.tx_hash,
        size=entry_tx.token_out_amount,
        realized_pnl=exit_tx.token_out_amount - entry_tx.token_in_amount,
        gas_fee_total=entry_tx.gas_fee_native + exit_tx.gas_fee_native,
        status="closed",
    )


def _open_record(entry_tx: RawTransaction) -> WalletTradeRecord:
    return WalletTradeRecord(
        token_symbol=entry_tx.token_out_symbol,
        direction="long",
        entry_price=entry_tx.token_in_amount / entry_tx.token_out_amount,
        entry_timestamp=entry_tx.timestamp,
        entry_tx_hash=entry_tx.tx_hash,
        exit_price=None,
        exit_timestamp=None,
        exit_tx_hash=None,
        size=entry_tx.token_out_amount,
        realized_pnl=None,
        gas_fee_total=entry_tx.gas_fee_native,
        status="open",
    )


def token_to_trading_pair(token_symbol: str, quote: str = "USDT") -> str:
    """A wallet trade's `token_symbol` is a bare token ("XRP"); the
    screener/snapshots key everything by trading-pair symbol ("XRPUSDT").
    This bridges the two — a v1 simplifying assumption that every token
    trades against USDT, matching confluence.data.providers' own
    convention. Good enough to look up "nearby criteria snapshots for
    this token" for the demo; a real implementation might need to know
    which pair a wallet actually traded against."""
    return f"{token_symbol.upper()}{quote}"


def normalize_transactions(
    transactions: list[RawTransaction],
    base_currencies: set[str] = WALLET_BASE_CURRENCIES,
) -> list[WalletTradeRecord]:
    ordered = sorted(transactions, key=lambda t: t.timestamp)
    open_entries: dict[str, deque[RawTransaction]] = defaultdict(deque)
    records: list[WalletTradeRecord] = []

    for tx in ordered:
        if _is_entry(tx, base_currencies):
            open_entries[tx.token_out_symbol].append(tx)
        elif _is_exit(tx, base_currencies):
            token = tx.token_in_symbol
            if open_entries[token]:
                entry_tx = open_entries[token].popleft()
                records.append(_closed_record(entry_tx, tx))
            # else: no matching entry seen in this scan (its history may
            # predate the scan window) -> no cost basis to pair against,
            # so this exit can't become a trade record. Skipped, not
            # guessed at.
        # else: a token-to-token swap not involving a base currency, or a
        # transfer between base currencies -- not modeled in v1.

    for entries in open_entries.values():
        for entry_tx in entries:
            records.append(_open_record(entry_tx))

    records.sort(key=lambda r: r.entry_timestamp)
    return records
