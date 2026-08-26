"""FastAPI application: serves the watchlist API and the static web UI.

API routes are registered before the static-file mount so they take
precedence — StaticFiles(html=True) is a catch-all that would otherwise
swallow every path, including /api/*.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from confluence.api.routes.watchlist import router as watchlist_router

STATIC_DIR = Path(__file__).resolve().parent / "static"


def create_app() -> FastAPI:
    app = FastAPI(
        title="Confluence",
        description=(
            "Descriptive multi-timeframe technical screening for a crypto watchlist. "
            "Reports factual technical state only — never a buy/sell recommendation."
        ),
    )
    app.include_router(watchlist_router, prefix="/api")
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
    return app


app = create_app()
