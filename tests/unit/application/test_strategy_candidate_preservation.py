"""Tests for preserving routed-out strategy alternatives."""

from datetime import UTC, datetime

from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.risk import RiskAssessment, RiskDecision, RiskRejectionCode
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    StrategyAnalysisResult,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.structure.regime import MarketRegime


NOW = datetime(2026, 7, 17, tzinfo=UTC)


def _candidate(strategy: StrategyType) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.9,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=95.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=110.0,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.7,
            volume_quality=0.7,
            liquidity_quality=0.7,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=("test evidence",),
        ),
        metadata={},
    )


def _phase4() -> StrategyAnalysisResult:
    candidates = (
        _candidate(StrategyType.TREND_PULLBACK),
        _candidate(StrategyType.BREAKOUT_CONTINUATION),
    )
    return StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=candidates,
        evaluated_strategies=tuple(StrategyType),
        eligible_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.BREAKOUT_CONTINUATION,
        ),
        decision_regime=MarketRegime.STRONG_UPTREND,
    )


def _assessment() -> RiskAssessment:
    return RiskAssessment(
        symbol="BTC/USDT",
        decision_time=NOW,
        decision=RiskDecision.REJECTED,
        setup=None,
        rejection_codes=(RiskRejectionCode.NO_SELECTED_CANDIDATE,),
        reasons=("no selected candidate",),
        configuration_id="test",
    )


def test_routing_preserves_disabled_generated_candidate_as_suppressed() -> None:
    routed = apply_strategy_routing(
        _phase4(),
        routing_config={"enabled": ["trend_pullback"]},
    )

    assert [candidate.strategy for candidate in routed.candidates] == [
        StrategyType.TREND_PULLBACK
    ]
    assert len(routed.suppressed_candidates) == 1
    suppressed = routed.suppressed_candidates[0]
    assert suppressed.candidate.strategy is StrategyType.BREAKOUT_CONTINUATION
    assert suppressed.reason_codes == ("STRATEGY_DISABLED_BY_CONFIG",)
    assert "disabled by configured strategy routing" in suppressed.reasons[0]


def test_routing_payload_exposes_suppressed_alternatives() -> None:
    routed = apply_strategy_routing(
        _phase4(),
        routing_config={"enabled": ["trend_pullback"]},
    )

    payload = build_strategy_routing_payload(
        assessment=_assessment(),
        strategy_analysis=routed,
        routing_config={"enabled": ["trend_pullback"]},
    )

    suppressed = payload["suppressed_candidates"]
    assert isinstance(suppressed, list)
    assert suppressed[0]["strategy"] == "breakout_continuation"
    assert suppressed[0]["routing_status"] == "suppressed"
    assert suppressed[0]["reason_codes"] == [
        "STRATEGY_DISABLED_BY_CONFIG"
    ]
