"""Morning report endpoint: ranks the current watchlist by how many of
the fixed criteria each ticker meets right now. All the actual ranking
logic lives in confluence/screening/report.py (deliberately UI-agnostic,
so it's ready for a future scheduler) — this route is just fetch +
serialize.
"""

from __future__ import annotations

import pandas as pd
from fastapi import APIRouter
from pydantic import BaseModel

from confluence.api.provider import DATA_SOURCE_LABEL, provider
from confluence.config import CANDLE_LIMIT
from confluence.data.fetch import fetch_universe_from_provider
from confluence.screening.analysis import build_ticker_report
from confluence.screening.report import generate_report
from confluence.watchlist import load_tickers

router = APIRouter(prefix="/report", tags=["report"])


class CriterionResultOut(BaseModel):
    key: str
    label: str
    met: bool


class TickerScoreOut(BaseModel):
    symbol: str
    met_count: int
    total_count: int
    criteria: list[CriterionResultOut]


class MorningReportResponse(BaseModel):
    generated_at: str
    data_source: str
    scores: list[TickerScoreOut]
    failed_symbols: list[str]  # watchlist tickers that couldn't be fetched, so weren't scored


@router.get("", response_model=MorningReportResponse)
def get_report() -> MorningReportResponse:
    symbols = load_tickers()
    raw = fetch_universe_from_provider(provider, symbols, limit=CANDLE_LIMIT)

    reports = {}
    failed_symbols = []
    for symbol, data in raw.items():
        if isinstance(data, Exception):
            failed_symbols.append(symbol)
            continue
        reports[symbol] = build_ticker_report(symbol, data)

    scores = [
        TickerScoreOut(
            symbol=score.symbol,
            met_count=score.met_count,
            total_count=score.total_count,
            criteria=[CriterionResultOut(key=c.key, label=c.label, met=c.met) for c in score.criteria],
        )
        for score in generate_report(reports)
    ]

    return MorningReportResponse(
        generated_at=pd.Timestamp.now(tz="UTC").isoformat(),
        data_source=DATA_SOURCE_LABEL,
        scores=scores,
        failed_symbols=failed_symbols,
    )
