from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import DiscoveryAssessment, SymbolAnalysis
from apex.application.public_output import (
    _methodology_no_trade_reason,
    _no_trade_reason_code,
)


def _analysis(*, all_suppressed: bool) -> SymbolAnalysis:
    decision_time = datetime(2026, 7, 18, tzinfo=UTC)
    return SymbolAnalysis(
        symbol="BTCUSDT",
        generated_at=decision_time,
        assessment=DiscoveryAssessment(
            symbol="BTCUSDT",
            decision_time=decision_time,
            setup=None,
            reasons=("phase 5 selected no setup",),
        ),
        candidate_count=2,
        evaluated_timeframes=("5m",),
        regime_by_timeframe={"5m": "stable_range"},
        data_quality_by_timeframe={"5m": {}},
        phase5_diagnostics={
            "methodology_candidate_routing": {
                "all_generated_candidates_suppressed": all_suppressed,
                "suppressed_strategies": ["trend_pullback", "range_reversal"],
            }
        },
    )


def test_all_methodology_suppressed_candidates_have_explicit_reason_code() -> None:
    analysis = _analysis(all_suppressed=True)

    assert _no_trade_reason_code(analysis) == "METHODOLOGY_ALL_CANDIDATES_SUPPRESSED"
    assert _methodology_no_trade_reason(analysis) == (
        "methodology suppressed all generated candidates: trend_pullback, range_reversal"
    )


def test_generic_no_trade_remains_when_methodology_did_not_remove_all_candidates() -> None:
    analysis = _analysis(all_suppressed=False)

    assert _no_trade_reason_code(analysis) == "NO_TRADE"
    assert _methodology_no_trade_reason(analysis) is None
