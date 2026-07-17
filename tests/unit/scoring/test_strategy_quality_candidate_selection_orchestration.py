"""Regression coverage for strategy-quality candidate-selection defaults."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.futures_quality import analyze_futures_phase5
from apex.domain import RiskMode
from apex.scoring import analyze_candidate_selection
from apex.strategies import StrategyAnalysisResult, StrategyType


def _empty_phase4() -> StrategyAnalysisResult:
    return StrategyAnalysisResult(
        symbol="BTCUSDT",
        decision_time=datetime(2026, 7, 14, tzinfo=UTC),
        candidates=(),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
    )


def test_futures_phase5_enables_standard_quality_gate_by_default() -> None:
    result = analyze_futures_phase5(_empty_phase4())

    assert result.metadata["strategy_quality_gate_enabled"] is True
    assert result.metadata["strategy_quality_risk_mode"] == RiskMode.STANDARD.value
    assert result.no_trade_reason == "no strategy candidates were generated"


def test_phase5_allows_explicit_research_opt_out() -> None:
    result = analyze_candidate_selection(_empty_phase4(), apply_strategy_quality=False)

    assert result.metadata["strategy_quality_gate_enabled"] is False
    assert result.metadata["strategy_quality_risk_mode"] == ""


