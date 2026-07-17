"""Tests for canonical deterministic strategy routing."""

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import cast

from apex.application.strategy_routing import apply_strategy_routing, build_strategy_routing_payload
from apex.risk import RiskAssessment, RiskDecision, RiskRejectionCode
from apex.strategies import StrategyAnalysisResult, StrategyType
from apex.structure.regime import MarketRegime

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ALL_STRATEGIES = tuple(StrategyType)


def _phase4() -> StrategyAnalysisResult:
    return StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(),
        evaluated_strategies=ALL_STRATEGIES,
        eligible_strategies=ALL_STRATEGIES,
        decision_regime=MarketRegime.BREAKOUT_EXPANSION,
    )


def _assessment() -> RiskAssessment:
    return RiskAssessment(
        symbol="BTC/USDT",
        decision_time=NOW,
        decision=RiskDecision.REJECTED,
        setup=None,
        rejection_codes=(RiskRejectionCode.NO_SELECTED_CANDIDATE,),
        reasons=("no selected candidate after routing",),
        configuration_id="test",
    )


def test_strategy_routing_filters_by_canonical_enabled_list() -> None:
    routed = apply_strategy_routing(_phase4(), routing_config={"enabled": ["trend_pullback"]})
    assert routed.eligible_strategies == (StrategyType.TREND_PULLBACK,)
    assert routed.skipped_strategies is not None
    assert "disabled by configured strategy routing" in routed.skipped_strategies[StrategyType.BREAKOUT_CONTINUATION]


def test_strategy_routing_payload_explains_regime_and_rejections() -> None:
    routed = apply_strategy_routing(_phase4(), routing_config={"enabled": ["trend_pullback"]})
    payload = build_strategy_routing_payload(
        assessment=_assessment(),
        strategy_analysis=routed,
        routing_config={"enabled": ["trend_pullback"]},
    )
    assert payload["decision_regime"] == "breakout_expansion"
    assert payload["routed_eligible_strategies"] == ["trend_pullback"]
    assert "scanner_type" not in payload
    assert "route_key" not in payload
    skipped_strategies = cast(Mapping[str, str], payload["skipped_strategies"])
    assert skipped_strategies["breakout_continuation"].startswith("breakout_continuation is disabled")
