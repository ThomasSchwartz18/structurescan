"""Watchlist endpoints: list tickers with their screened state, add/remove
tickers. Every response reports descriptive technical state only — see
confluence/screening/analysis.py for the "facts, not verdicts" rule this
whole app is built around.

See confluence/api/provider.py for the shared DataProvider instance used
across every route in this app, including paper trading.
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from confluence.api.provider import DATA_SOURCE_LABEL, provider
from confluence.api.schemas import BtcContextOut, WatchlistResponse, to_ticker_row
from confluence.config import BTC_REFERENCE_SYMBOL, CANDLE_LIMIT
from confluence.data.fetch import fetch_ticker_from_provider, fetch_universe_from_provider
from confluence.screening.analysis import build_ticker_report
from confluence.watchlist import load_tickers, save_tickers

router = APIRouter(tags=["watchlist"])


class AddTickerRequest(BaseModel):
    symbol: str


def build_btc_context() -> Optional[BtcContextOut]:
    """Always-visible market context, independent of the user's watchlist.
    Best-effort: if BTC itself can't be fetched, the reference row is just
    omitted rather than failing the whole watchlist response."""
    try:
        data = fetch_ticker_from_provider(provider, BTC_REFERENCE_SYMBOL, timeframe_labels=["1D"], limit=CANDLE_LIMIT)
        report = build_ticker_report(BTC_REFERENCE_SYMBOL, data)
    except Exception:  # noqa: BLE001 - reference context is best-effort
        return None
    return BtcContextOut(symbol=BTC_REFERENCE_SYMBOL, ma_stack=report.timeframes["1D"].ma_stack)


def _build_watchlist_response() -> WatchlistResponse:
    symbols = load_tickers()
    raw = fetch_universe_from_provider(provider, symbols, limit=CANDLE_LIMIT)

    rows = []
    for symbol in symbols:  # preserve the user's list order
        data = raw[symbol]
        if isinstance(data, Exception):
            rows.append(to_ticker_row(symbol, error=str(data)))
            continue
        try:
            current_price = provider.get_current_price(symbol)
        except Exception as exc:  # noqa: BLE001 - isolate one bad ticker from the rest
            rows.append(to_ticker_row(symbol, error=str(exc)))
            continue
        report = build_ticker_report(symbol, data)
        rows.append(to_ticker_row(symbol, report=report, current_price=current_price))

    return WatchlistResponse(
        data_source=DATA_SOURCE_LABEL,
        generated_at=pd.Timestamp.now(tz="UTC").isoformat(),
        btc_context=build_btc_context(),
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
