"""Tests for scanner candidate diagnostic visibility."""

from datetime import UTC, datetime

from apex.application.strategy_routing import _candidate_diagnostics
from apex.domain import EntryState
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
from apex.strategies.diagnostics import Phase4RejectionCode, StrategyDiagnostic
from apex.structure.regime import MarketRegime


def _candidate(decision_time: datetime) -> TradeCandidate:
    return TradeCandidate(
        symbol="TEST/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=decision_time,
        entry=EntryZone(
            lower=99.5,
            upper=100.5,
            preferred=100.0,
            current_price=100.2,
            distance_from_current=0.2,
            atr_distance=0.2,
            estimated_move_missed=0.0,
            location_quality=0.82,
            mode=EntryMode.RETEST,
            rationale=("controlled retest",),
            max_chase_price=101.0,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.5,
            rationale=("structure fails below support",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=103.0,
                    label="TP1",
                    rationale=("prior swing high",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.82,
            momentum_quality=0.7,
            volume_quality=0.7,
            liquidity_quality=0.6,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(supporting=("trend and retest align",)),
        metadata={"retest_trigger": 100.1},
    )


def test_candidate_diagnostics_preserve_geometry_and_missing_values() -> None:
    decision_time = datetime(2026, 7, 16, tzinfo=UTC)
    candidate = _candidate(decision_time)
    phase4 = StrategyAnalysisResult(
        symbol="TEST/USDT",
        decision_time=decision_time,
        candidates=(candidate,),
        evaluated_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.RANGE_REVERSAL,
        ),
        eligible_strategies=(StrategyType.TREND_PULLBACK,),
        skipped_strategies={
            StrategyType.RANGE_REVERSAL: "range reversal is not routed in this regime"
        },
        strategy_diagnostics={
            StrategyType.TREND_PULLBACK: StrategyDiagnostic(
                strategy=StrategyType.TREND_PULLBACK,
                candidate_count=1,
                rejection_codes=(),
                reasons=("strategy generated at least one raw candidate",),
                near_miss_state=EntryState.READY_NOW,
            ),
            StrategyType.RANGE_REVERSAL: StrategyDiagnostic(
                strategy=StrategyType.RANGE_REVERSAL,
                candidate_count=0,
                rejection_codes=(Phase4RejectionCode.REGIME_INELIGIBLE,),
                reasons=("range reversal is not routed in this regime",),
                near_miss_state=EntryState.NO_TRADE,
            ),
        },
        decision_regime=MarketRegime.STRONG_UPTREND,
    )

    records = _candidate_diagnostics(phase4)

    generated = records[0]
    assert generated["generated"] is True
    assert generated["entry_zone_low"] == 99.5
    assert generated["entry_zone_high"] == 100.5
    assert generated["ideal_entry"] == 100.0
    assert generated["maximum_chase_price"] == 101.0
    assert generated["current_price"] == 100.2
    assert generated["entry_quality"] == 82.0
    assert generated["nearest_future_trigger"] == 100.1
    assert generated["invalidation"] == 98.5
    assert generated["candidate_score"] is None

    not_generated = records[1]
    assert not_generated["generated"] is False
    assert not_generated["direction"] is None
    assert not_generated["entry_zone_low"] is None
    assert not_generated["candidate_score"] is None
    assert not_generated["rejection_codes"] == ["regime_ineligible"]
    assert not_generated["near_miss_state"] == "NO_TRADE"
