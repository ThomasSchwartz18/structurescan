"""The single place that selects which WalletProvider backs the wallet
scan feature — mirrors confluence/api/provider.py for DataProvider.
MockWalletProvider today; a future RealWalletProvider (reading from a
public RPC/explorer API using just a public address, read-only) swaps in
here with no other code changes.
"""

from __future__ import annotations

from confluence.wallet.providers.base import WalletProvider
from confluence.wallet.providers.mock_provider import MockWalletProvider

wallet_provider: WalletProvider = MockWalletProvider()
WALLET_DATA_SOURCE_LABEL = "mock"
