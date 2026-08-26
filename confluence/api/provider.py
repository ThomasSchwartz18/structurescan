"""The single place that selects which DataProvider backs the web app.

Both the watchlist/screening routes and the paper trading routes import
`provider` from here, so they always see the same data source.

Controlled by the CONFLUENCE_DATA_PROVIDER environment variable (see
SETUP.md): "mock" (default) or "real". RealDataProvider wraps Binance's
public REST API and needs no API key — see confluence/data/providers/
real_provider.py. Nothing in the screening, indicator, or paper trading
layers has to know which one is active.
"""

from __future__ import annotations

import os

from confluence.data.providers.base import DataProvider
from confluence.data.providers.mock_provider import MockDataProvider
from confluence.data.providers.real_provider import RealDataProvider


def select_provider(env_value: str) -> tuple[DataProvider, str]:
    """Pure selection logic, kept separate from the module-level globals
    below so it's testable without import-time/reload gymnastics."""
    if env_value.strip().lower() == "real":
        return RealDataProvider(), "real"
    return MockDataProvider(), "mock"


provider, DATA_SOURCE_LABEL = select_provider(os.getenv("CONFLUENCE_DATA_PROVIDER", "mock"))
