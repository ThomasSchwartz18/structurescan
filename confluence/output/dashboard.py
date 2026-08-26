"""Render ticker reports as a terminal table.

Every cell here reports observed state (MA stack, RSI zone, swing structure,
alignment/conflict between timeframes). None of it is a buy/sell signal —
"aligned_bullish" describes that timeframes agree on a bullish technical
state, it is not an instruction to act.
"""

from __future__ import annotations

from rich.table import Table

from confluence.screening.analysis import TickerReport, TimeframeState

STRUCTURE_LABELS = {
    "higher_highs_higher_lows": "HH/HL",
    "lower_highs_lower_lows": "LH/LL",
    "mixed": "mixed",
    "insufficient_data": "n/a",
}

ALIGNMENT_LABELS = {
    "aligned_bullish": "aligned (bullish)",
    "aligned_bearish": "aligned (bearish)",
    "conflict": "conflict",
}

DISPLAY_TIMEFRAMES = ["1D", "4H", "1H", "15min"]

COLUMNS = [
    "Symbol",
    "1D MA Stack",
    "1D RSI",
    "1D Structure",
    "4H Structure",
    "1H Structure",
    "15min Structure",
    "1D Swing Low",
    "1D Swing High",
    "Alignment",
]


def format_structure(structure: str) -> str:
    return STRUCTURE_LABELS.get(structure, structure)


def format_rsi(state: TimeframeState) -> str:
    if state.rsi is None:
        return "n/a"
    return f"{state.rsi:.1f} ({state.rsi_zone})"


def format_swing(ref) -> str:
    if ref is None:
        return "n/a"
    return f"{ref.price:.4f}"


def format_alignment(alignment: str) -> str:
    return ALIGNMENT_LABELS.get(alignment, alignment)


def build_table(reports: dict[str, TickerReport | Exception]) -> Table:
    table = Table(title="Confluence — technical state screen (descriptive only, not a recommendation)")
    for col in COLUMNS:
        table.add_column(col)

    for symbol, report in reports.items():
        if isinstance(report, Exception):
            table.add_row(symbol, *(["error: " + str(report)] + ["-"] * (len(COLUMNS) - 2)))
            continue

        d1 = report.timeframes.get("1D")
        h4 = report.timeframes.get("4H")
        h1 = report.timeframes.get("1H")
        m15 = report.timeframes.get("15min")

        table.add_row(
            symbol,
            d1.ma_stack if d1 else "n/a",
            format_rsi(d1) if d1 else "n/a",
            format_structure(d1.structure) if d1 else "n/a",
            format_structure(h4.structure) if h4 else "n/a",
            format_structure(h1.structure) if h1 else "n/a",
            format_structure(m15.structure) if m15 else "n/a",
            format_swing(d1.nearest_swing_low) if d1 else "n/a",
            format_swing(d1.nearest_swing_high) if d1 else "n/a",
            format_alignment(report.alignment),
        )

    return table
