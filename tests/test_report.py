from confluence.config import REPORT_RR_RATIO_MIN
from confluence.screening.analysis import TickerReport, TimeframeState
from confluence.screening.report import (
    CORE_ALIGNMENT_TIMEFRAMES,
    evaluate_criteria,
    generate_report,
    score_ticker,
)


def _state(
    timeframe="1D",
    bias_state="bullish_state",
    ma_stack="bullish",
    rsi_zone="neutral",
    ma20_state="normal",
    volume_state="confirmed",
    rsi_divergence="none",
):
    return TimeframeState(
        timeframe=timeframe,
        last_close=100.0,
        rsi=50.0,
        rsi_zone=rsi_zone,
        ma_values={20: 99, 50: 98, 100: 97, 200: 96},
        ma_stack=ma_stack,
        price_vs_ma={20: "above", 50: "above", 100: "above", 200: "above"},
        structure="higher_highs_higher_lows",
        nearest_swing_high=None,
        nearest_swing_low=None,
        bias_state=bias_state,
        ma20_state=ma20_state,
        volume_state=volume_state,
        rsi_divergence=rsi_divergence,
    )


def _report(symbol="AAAUSDT", timeframes=None, rr_ratio=2.0, alignment="aligned_bullish"):
    if timeframes is None:
        timeframes = {label: _state(label) for label in ["1D", "4H", "1H", "15min"]}
    return TickerReport(symbol=symbol, timeframes=timeframes, alignment=alignment, rr_ratio=rr_ratio)


def test_all_criteria_met():
    report = _report()
    results = evaluate_criteria(report)
    assert all(r.met for r in results)
    assert len(results) == 6


def test_no_criteria_met():
    # A definite (not "mixed") ma_stack is required here: "mixed" would
    # trivially satisfy the divergence criterion by design (see
    # test_no_conflicting_divergence_mixed_stack_is_trivially_satisfied),
    # which would defeat the point of this "everything fails" case.
    daily = _state(
        bias_state="mixed_state",
        ma_stack="bullish",
        rsi_zone="overbought",
        ma20_state="extended",
        volume_state="weak",
        rsi_divergence="bearish",
    )
    other = _state("4H", bias_state="bearish_state", ma_stack="bearish")
    report = _report(
        timeframes={"1D": daily, "4H": other, "1H": other, "15min": other},
        rr_ratio=1.0,  # below threshold
    )
    results = evaluate_criteria(report)
    assert all(not r.met for r in results)


def test_core_alignment_uses_only_1d_4h_1h_not_15min():
    # 15min deliberately disagrees; per the user's own wording this
    # criterion is scoped to daily/4H/1H only, so it should still pass.
    states = {
        "1D": _state("1D", bias_state="bullish_state"),
        "4H": _state("4H", bias_state="bullish_state"),
        "1H": _state("1H", bias_state="bullish_state"),
        "15min": _state("15min", bias_state="bearish_state"),
    }
    report = _report(timeframes=states, alignment="conflict")  # full alignment IS conflict
    results = evaluate_criteria(report)
    alignment_result = next(r for r in results if r.key == "alignment")
    assert alignment_result.met is True


def test_core_alignment_fails_when_1h_disagrees():
    states = {
        "1D": _state("1D", bias_state="bullish_state"),
        "4H": _state("4H", bias_state="bullish_state"),
        "1H": _state("1H", bias_state="bearish_state"),
        "15min": _state("15min", bias_state="bullish_state"),
    }
    report = _report(timeframes=states)
    results = evaluate_criteria(report)
    alignment_result = next(r for r in results if r.key == "alignment")
    assert alignment_result.met is False


def test_core_alignment_fails_when_required_timeframe_missing():
    states = {"1D": _state("1D"), "4H": _state("4H")}  # no 1H
    report = _report(timeframes=states)
    results = evaluate_criteria(report)
    alignment_result = next(r for r in results if r.key == "alignment")
    assert alignment_result.met is False


def test_no_conflicting_divergence_bullish_stack_vs_bearish_divergence():
    daily = _state(ma_stack="bullish", rsi_divergence="bearish")
    report = _report(timeframes={"1D": daily, "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")})
    result = next(r for r in evaluate_criteria(report) if r.key == "no_conflicting_divergence")
    assert result.met is False


def test_no_conflicting_divergence_bullish_stack_vs_bullish_divergence_is_fine():
    daily = _state(ma_stack="bullish", rsi_divergence="bullish")
    report = _report(timeframes={"1D": daily, "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")})
    result = next(r for r in evaluate_criteria(report) if r.key == "no_conflicting_divergence")
    assert result.met is True


def test_no_conflicting_divergence_bearish_stack_vs_bullish_divergence():
    daily = _state(ma_stack="bearish", rsi_divergence="bullish")
    report = _report(timeframes={"1D": daily, "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")})
    result = next(r for r in evaluate_criteria(report) if r.key == "no_conflicting_divergence")
    assert result.met is False


def test_no_conflicting_divergence_mixed_stack_is_trivially_satisfied():
    daily = _state(ma_stack="mixed", rsi_divergence="bearish")
    report = _report(timeframes={"1D": daily, "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")})
    result = next(r for r in evaluate_criteria(report) if r.key == "no_conflicting_divergence")
    assert result.met is True


def test_rr_ratio_criterion_is_strictly_above_threshold():
    report_at_threshold = _report(rr_ratio=REPORT_RR_RATIO_MIN)
    report_above_threshold = _report(rr_ratio=REPORT_RR_RATIO_MIN + 0.01)

    at = next(r for r in evaluate_criteria(report_at_threshold) if r.key == "rr_ratio")
    above = next(r for r in evaluate_criteria(report_above_threshold) if r.key == "rr_ratio")
    assert at.met is False
    assert above.met is True


def test_rr_ratio_criterion_unmet_when_none():
    report = _report(rr_ratio=None)
    result = next(r for r in evaluate_criteria(report) if r.key == "rr_ratio")
    assert result.met is False


def test_score_ticker_counts_met_criteria():
    report = _report()  # meets all 6
    score = score_ticker(report)
    assert score.symbol == "AAAUSDT"
    assert score.met_count == 6
    assert score.total_count == 6


def test_generate_report_ranks_highest_first():
    good = _report(symbol="GOODUSDT")  # 6/6
    bad_daily = _state(rsi_zone="overbought", ma20_state="extended")
    bad = _report(
        symbol="BADUSDT",
        timeframes={"1D": bad_daily, "4H": _state("4H"), "1H": _state("1H"), "15min": _state("15min")},
        rr_ratio=0.5,
    )

    ranked = generate_report({"BADUSDT": bad, "GOODUSDT": good})
    assert [s.symbol for s in ranked] == ["GOODUSDT", "BADUSDT"]
    assert ranked[0].met_count > ranked[1].met_count


def test_generate_report_ties_broken_alphabetically():
    a = _report(symbol="BBBUSDT")
    b = _report(symbol="AAAUSDT")
    ranked = generate_report({"BBBUSDT": a, "AAAUSDT": b})
    assert [s.symbol for s in ranked] == ["AAAUSDT", "BBBUSDT"]


def test_core_alignment_timeframes_constant_excludes_15min():
    assert "15min" not in CORE_ALIGNMENT_TIMEFRAMES
    assert set(CORE_ALIGNMENT_TIMEFRAMES) == {"1D", "4H", "1H"}
