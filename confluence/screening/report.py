"""Morning report: rank watchlist tickers by how many user-defined
criteria they currently meet right now.

This is transparent criteria-matching, not a verdict: it reports
"X meets 5/6 of your defined criteria: [...]", never "focus on X" or
"best setup today". No function here should ever be extended to rank,
phrase, or highlight a ticker as a thing to act on — only to state which
of the fixed criteria below are currently true for it.

Kept independent of any HTTP/UI concern on purpose: `generate_report()`
takes already-built TickerReport objects and returns plain data, so it's
directly callable from a future scheduler (e.g. a morning cron job) with
no changes here — only something new choosing to call it on a timer.
"""

from __future__ import annotations

from dataclasses import dataclass

from confluence.config import REPORT_RR_RATIO_MIN
from confluence.screening.analysis import TickerReport, TimeframeState

CORE_ALIGNMENT_TIMEFRAMES = ("1D", "4H", "1H")


@dataclass
class CriterionResult:
    key: str
    label: str
    met: bool


@dataclass
class TickerScore:
    symbol: str
    criteria: list[CriterionResult]
    met_count: int
    total_count: int


def _core_alignment_met(report: TickerReport) -> bool:
    """Criterion (a): "daily/4H/1H alignment" — deliberately just those
    three timeframes (per the user's own wording), not the full 4-way
    alignment (which also includes 15min) shown in the watchlist table."""
    states = [report.timeframes[label] for label in CORE_ALIGNMENT_TIMEFRAMES if label in report.timeframes]
    if len(states) < len(CORE_ALIGNMENT_TIMEFRAMES):
        return False
    biases = {state.bias_state for state in states}
    return biases in ({"bullish_state"}, {"bearish_state"})


def _no_conflicting_divergence(daily: TimeframeState | None) -> bool:
    """Criterion (e): "no bearish divergence if considering a long / no
    bullish divergence if considering a short" (user's own wording). The
    report has no separate input for "which direction the user is
    considering" — so the daily MA stack's own direction stands in for
    it: a bullish-stacked daily trend is checked against bearish
    divergence, a bearish-stacked one against bullish divergence. A
    mixed/insufficient daily stack has no direction to check against, so
    this criterion is trivially satisfied (nothing to conflict with)."""
    if daily is None:
        return False
    if daily.ma_stack == "bullish":
        return daily.rsi_divergence != "bearish"
    if daily.ma_stack == "bearish":
        return daily.rsi_divergence != "bullish"
    return True


def evaluate_criteria(report: TickerReport) -> list[CriterionResult]:
    daily = report.timeframes.get("1D")

    return [
        CriterionResult(
            key="alignment",
            label="Daily/4H/1H timeframes aligned",
            met=_core_alignment_met(report),
        ),
        CriterionResult(
            key="rsi_neutral",
            label="Daily RSI in neutral zone",
            met=daily is not None and daily.rsi_zone == "neutral",
        ),
        CriterionResult(
            key="ma20_not_extended",
            label="Not extended >5% from daily 20-MA",
            met=daily is not None and daily.ma20_state == "normal",
        ),
        CriterionResult(
            key="volume_confirming",
            label="Daily volume confirming (not weak)",
            met=daily is not None and daily.volume_state == "confirmed",
        ),
        CriterionResult(
            key="no_conflicting_divergence",
            label="No RSI divergence against the daily trend direction",
            met=_no_conflicting_divergence(daily),
        ),
        CriterionResult(
            key="rr_ratio",
            label=f"Risk/reward above {REPORT_RR_RATIO_MIN:g}:1",
            met=report.rr_ratio is not None and report.rr_ratio > REPORT_RR_RATIO_MIN,
        ),
    ]


def score_ticker(report: TickerReport) -> TickerScore:
    criteria = evaluate_criteria(report)
    met_count = sum(1 for c in criteria if c.met)
    return TickerScore(symbol=report.symbol, criteria=criteria, met_count=met_count, total_count=len(criteria))


def generate_report(reports: dict[str, TickerReport]) -> list[TickerScore]:
    """Rank tickers by how many criteria they currently meet, highest
    first. Ties broken alphabetically by symbol for a stable,
    reproducible order (not by any notion of which is "better")."""
    scores = [score_ticker(report) for report in reports.values()]
    scores.sort(key=lambda s: (-s.met_count, s.symbol))
    return scores
