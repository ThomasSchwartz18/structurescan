"""Criteria snapshot lookup — currently just the "nearby snapshots for
this symbol around this time" query the wallet-trade annotation UI uses
to let the user pick which historical screener state to link, instead of
typing anything by hand.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from confluence.snapshots.db import get_connection
from confluence.snapshots.store import Snapshot, nearby_snapshots

router = APIRouter(prefix="/snapshots", tags=["snapshots"])


class SnapshotSummaryOut(BaseModel):
    id: int
    symbol: str
    captured_at: str
    alignment: Optional[str] = None
    rr_ratio: Optional[float] = None
    daily_ma_stack: Optional[str] = None
    daily_rsi: Optional[float] = None


class NearbySnapshotsResponse(BaseModel):
    symbol: str
    snapshots: list[SnapshotSummaryOut]


def _summarize(snapshot: Snapshot) -> SnapshotSummaryOut:
    payload = snapshot.payload
    daily = payload.get("timeframes", {}).get("1D", {}) or {}
    return SnapshotSummaryOut(
        id=snapshot.id,
        symbol=snapshot.symbol,
        captured_at=snapshot.captured_at,
        alignment=payload.get("alignment"),
        rr_ratio=payload.get("rr_ratio"),
        daily_ma_stack=daily.get("ma_stack"),
        daily_rsi=daily.get("rsi"),
    )


@router.get("/{symbol}/nearby", response_model=NearbySnapshotsResponse)
def get_nearby_snapshots(symbol: str, around: str, count: int = 5) -> NearbySnapshotsResponse:
    if count < 1:
        raise HTTPException(status_code=400, detail="count must be >= 1")
    conn = get_connection()
    try:
        snapshots = nearby_snapshots(conn, symbol.upper(), around, count=count)
    finally:
        conn.close()
    return NearbySnapshotsResponse(symbol=symbol.upper(), snapshots=[_summarize(s) for s in snapshots])
