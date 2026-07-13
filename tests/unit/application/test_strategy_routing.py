"""Tests for deterministic scanner/regime/gainer strategy routing."""

from datetime import UTC, datetime

from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.domain import GainerState, GainerStateResult, MarketCategory
from apex.risk import RiskAssessment, RiskDecision, RiskRejectionCode
from apex.strategies import Phase4AnalysisResult, StrategyType
from apex.structure.regime import MarketRegime

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ALL_STRATEGIES = tuple(StrategyType)


def _phase4() -> Phase4AnalysisResult:
    return Phase4AnalysisResult(
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


def test_strategy_routing_filters_candidates_by_scanner_route() -> None:
    routed = apply_strategy_routing(
        _phase4(),
        scanner_type=MarketCategory.GAINER,
        gainer_result=GainerStateResult(
            state=GainerState.ACCELERATION,
            evidence=("rapid gainer",),
        ),
        routing_config={
            "normal_market": ["trend_pullback"],
            "gainer": ["momentum_gainer_continuation"],
        },
    )

    assert routed.eligible_strategies == (StrategyType.MOMENTUM_GAINER_CONTINUATION,)
    assert (
        "disabled by configured gainer scanner route"
        in routed.skipped_strategies[StrategyType.TREND_PULLBACK]
    )


def test_strategy_routing_rejects_unfavorable_gainer_state() -> None:
    routed = apply_strategy_routing(
        _phase4(),
        scanner_type=MarketCategory.GAINER,
        gainer_result=GainerStateResult(
            state=GainerState.DISTRIBUTION,
            evidence=("weak close",),
        ),
        routing_config={
            "normal_market": ["trend_pullback"],
            "gainer": ["momentum_gainer_continuation"],
        },
    )

    assert StrategyType.MOMENTUM_GAINER_CONTINUATION not in routed.eligible_strategies
    assert (
        "requires fresh, accelerating, or controlled gainer state"
        in routed.skipped_strategies[StrategyType.MOMENTUM_GAINER_CONTINUATION]
    )


def test_strategy_routing_payload_explains_regime_and_route_rejections() -> None:
    routed = apply_strategy_routing(
        _phase4(),
        scanner_type=MarketCategory.NORMAL_MARKET,
        gainer_result=None,
        routing_config={
            "normal_market": ["trend_pullback"],
            "gainer": ["momentum_gainer_continuation"],
        },
    )
    payload = build_strategy_routing_payload(
        scanner_type=MarketCategory.NORMAL_MARKET,
        assessment=_assessment(),
        gainer_result=None,
        phase4=routed,
        routing_config={
            "normal_market": ["trend_pullback"],
            "gainer": ["momentum_gainer_continuation"],
        },
    )

    assert payload["decision_regime"] == "breakout_expansion"
    assert payload["routed_eligible_strategies"] == ["trend_pullback"]
    assert payload["skipped_strategies"]["breakout_continuation"].startswith(
        "breakout_continuation is disabled"
    )
