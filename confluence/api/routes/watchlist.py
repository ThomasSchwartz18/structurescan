"""Watchlist endpoints: list tickers with their screened state, add/remove
tickers. Every response reports descriptive technical state only — see
confluence/screening/analysis.py for the "facts, not verdicts" rule this
whole app is built around.

`_provider` is the single place that selects which DataProvider backs
this API. It's MockDataProvider today; swapping in a future
RealDataProvider (implementing the same interface) is the only change
this pivot requires — nothing else in this file, or in the screening/
indicator layers, needs to know.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from confluence.api.schemas import WatchlistResponse, to_ticker_row
from confluence.config import CANDLE_LIMIT
from confluence.data.fetch import fetch_universe_from_provider
from confluence.data.providers.base import DataProvider
from confluence.data.providers.mock_provider import MockDataProvider
from confluence.screening.analysis import build_ticker_report
from confluence.watchlist import load_tickers, save_tickers

router = APIRouter(tags=["watchlist"])

_provider: DataProvider = MockDataProvider()
DATA_SOURCE_LABEL = "mock"


class AddTickerRequest(BaseModel):
    symbol: str


def _build_watchlist_response() -> WatchlistResponse:
    symbols = load_tickers()
    raw = fetch_universe_from_provider(_provider, symbols, limit=CANDLE_LIMIT)

    rows = []
    for symbol in symbols:  # preserve the user's list order
        data = raw[symbol]
        if isinstance(data, Exception):
            rows.append(to_ticker_row(symbol, error=str(data)))
            continue
        try:
            current_price = _provider.get_current_price(symbol)
        except Exception as exc:  # noqa: BLE001 - isolate one bad ticker from the rest
            rows.append(to_ticker_row(symbol, error=str(exc)))
            continue
        report = build_ticker_report(symbol, data)
        rows.append(to_ticker_row(symbol, report=report, current_price=current_price))

    return WatchlistResponse(
        data_source=DATA_SOURCE_LABEL,
        generated_at=pd.Timestamp.now(tz="UTC").isoformat(),
        tickers=rows,
    )


@router.get("/watchlist", response_model=WatchlistResponse)
def get_watchlist() -> WatchlistResponse:
    return _build_watchlist_response()


@router.post("/watchlist", response_model=WatchlistResponse)
def add_ticker(payload: AddTickerRequest) -> WatchlistResponse:
    symbol = payload.symbol.strip().upper()
    if not symbol:
        raise HTTPException(status_code=400, detail="symbol is required")

    tickers = load_tickers()
    if symbol not in tickers:
        tickers.append(symbol)
        save_tickers(tickers)
    return _build_watchlist_response()


@router.delete("/watchlist/{symbol}", response_model=WatchlistResponse)
def remove_ticker(symbol: str) -> WatchlistResponse:
    symbol = symbol.strip().upper()
    tickers = load_tickers()
    if symbol in tickers:
        tickers.remove(symbol)
        save_tickers(tickers)
    return _build_watchlist_response()


@router.get("/meta")
def get_meta() -> dict:
    return {"data_source": DATA_SOURCE_LABEL}
