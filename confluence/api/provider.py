"""The single place that selects which DataProvider backs the web app.

Both the watchlist/screening routes and the paper trading routes import
`provider` from here, so they always see the same data source. It's
MockDataProvider today; swapping in a future RealDataProvider
(implementing the same interface) is the only change needed anywhere —
nothing in the screening, indicator, or paper trading layers has to know.
"""

from __future__ import annotations

from confluence.data.providers.base import DataProvider
from confluence.data.providers.mock_provider import MockDataProvider

provider: DataProvider = MockDataProvider()
DATA_SOURCE_LABEL = "mock"
