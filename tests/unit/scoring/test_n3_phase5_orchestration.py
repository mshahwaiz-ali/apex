"""Regression coverage for N3 Phase 5 orchestration defaults."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.domain import RiskMode
from apex.scoring import analyze_phase5
from apex.strategies import Phase4AnalysisResult, StrategyType


def _empty_phase4() -> Phase4AnalysisResult:
    return Phase4AnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 14, tzinfo=UTC),
        candidates=(),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
    )


def test_phase5_enables_standard_quality_gate_by_default() -> None:
    result = analyze_phase5(_empty_phase4())

    assert result.metadata["strategy_quality_gate_enabled"] is True
    assert result.metadata["strategy_quality_risk_mode"] == RiskMode.STANDARD.value
    assert result.no_trade_reason == "no Phase 4 candidates were generated"


def test_phase5_allows_explicit_research_opt_out() -> None:
    result = analyze_phase5(_empty_phase4(), apply_strategy_quality=False)

    assert result.metadata["strategy_quality_gate_enabled"] is False
    assert result.metadata["strategy_quality_risk_mode"] == ""


def test_phase5_supports_explicit_aggressive_mode() -> None:
    result = analyze_phase5(_empty_phase4(), risk_mode=RiskMode.AGGRESSIVE)

    assert result.metadata["strategy_quality_gate_enabled"] is True
    assert result.metadata["strategy_quality_risk_mode"] == RiskMode.AGGRESSIVE.value
