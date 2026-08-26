"""Wallet-scan journal endpoints: scan a public wallet address for swap
history, review/annotate the resulting trade records, and view stats
(including a breakdown by how many report criteria were met at entry).

Read-only, same as the rest of this feature: `scan_wallet` only ever
calls WalletProvider.get_transactions(address, ...) — there is no path
here that signs or broadcasts anything.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict

from confluence.api.wallet_provider import WALLET_DATA_SOURCE_LABEL, wallet_provider
from confluence.config import DEFAULT_WALLET_CHAIN
from confluence.screening.report import score_ticker
from confluence.snapshots.db import get_connection as get_snapshots_connection
from confluence.snapshots.store import get_snapshot, reconstruct_report
from confluence.wallet.db import get_connection as get_wallet_connection
from confluence.wallet.normalize import normalize_transactions
from confluence.wallet.store import (
    WalletJournalError,
    WalletStats,
    WalletTrade,
    annotate_trade,
    compute_wallet_stats,
    get_wallet_trade,
    ingest_trade_records,
    list_logged,
    list_needs_review,
)

router = APIRouter(prefix="/wallet", tags=["wallet"])


class ScanRequest(BaseModel):
    address: str
    chain: str = DEFAULT_WALLET_CHAIN


class ScanResponse(BaseModel):
    address: str
    chain: str
    data_source: str
    transactions_found: int
    trade_records_found: int
    new_trades_ingested: int


class AnnotateRequest(BaseModel):
    reasoning: str
    linked_snapshot_id: Optional[int] = None


class WalletTradeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    token_symbol: str
    direction: str
    entry_price: float
    entry_timestamp: str
    entry_tx_hash: str
    exit_price: Optional[float]
    exit_timestamp: Optional[str]
    exit_tx_hash: Optional[str]
    size: float
    realized_pnl: Optional[float]
    gas_fee_total: float
    position_status: str
    review_status: str
    reasoning: Optional[str]
    linked_snapshot_id: Optional[int]
    criteria_met_count: Optional[int]
    criteria_total_count: Optional[int]
    annotated_at: Optional[str]


class CriteriaBucketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    met_count: int
    total_count: int
    trade_count: int
    win_count: int
    total_pnl: float
    win_rate: Optional[float]


class WalletStatsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    logged_count: int
    closed_count: int
    total_realized_pnl: float
    total_gas_fees: float
    win_count: int
    loss_count: int
    win_rate: Optional[float]
    avg_win: Optional[float]
    avg_loss: Optional[float]
    by_criteria: list[CriteriaBucketOut]


@router.post("/scan", response_model=ScanResponse)
def scan_wallet(payload: ScanRequest) -> ScanResponse:
    address = payload.address.strip()
    if not address:
        raise HTTPException(status_code=400, detail="address is required")

    try:
        transactions = wallet_provider.get_transactions(address, chain=payload.chain)
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
        raise HTTPException(status_code=502, detail=f"could not fetch wallet transactions: {exc}")

    records = normalize_transactions(transactions)

    conn = get_wallet_connection()
    try:
        inserted = ingest_trade_records(conn, records)
    finally:
        conn.close()

    return ScanResponse(
        address=address,
        chain=payload.chain,
        data_source=WALLET_DATA_SOURCE_LABEL,
        transactions_found=len(transactions),
        trade_records_found=len(records),
        new_trades_ingested=inserted,
    )


@router.get("/needs-review", response_model=list[WalletTradeOut])
def get_needs_review() -> list[WalletTrade]:
    conn = get_wallet_connection()
    try:
        return list_needs_review(conn)
    finally:
        conn.close()


@router.get("/logged", response_model=list[WalletTradeOut])
def get_logged() -> list[WalletTrade]:
    conn = get_wallet_connection()
    try:
        return list_logged(conn)
    finally:
        conn.close()


@router.post("/trades/{trade_id}/annotate", response_model=WalletTradeOut)
def annotate(trade_id: int, payload: AnnotateRequest) -> WalletTrade:
    conn = get_wallet_connection()
    try:
        get_wallet_trade(conn, trade_id)  # raises WalletJournalError -> 404 if unknown
    except WalletJournalError as exc:
        conn.close()
        raise HTTPException(status_code=404, detail=str(exc))

    criteria_met_count = None
    criteria_total_count = None
    if payload.linked_snapshot_id is not None:
        snap_conn = get_snapshots_connection()
        try:
            snapshot = get_snapshot(snap_conn, payload.linked_snapshot_id)
        finally:
            snap_conn.close()
        if snapshot is not None:
            score = score_ticker(reconstruct_report(snapshot))
            criteria_met_count = score.met_count
            criteria_total_count = score.total_count

    try:
        trade = annotate_trade(
            conn,
            trade_id,
            payload.reasoning,
            linked_snapshot_id=payload.linked_snapshot_id,
            criteria_met_count=criteria_met_count,
            criteria_total_count=criteria_total_count,
        )
    except WalletJournalError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    finally:
        conn.close()
    return trade


@router.get("/stats", response_model=WalletStatsOut)
def get_stats() -> WalletStats:
    conn = get_wallet_connection()
    try:
        return compute_wallet_stats(conn)
    finally:
        conn.close()
