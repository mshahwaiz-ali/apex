from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.contracts import (
    CandidateLifecycle,
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.opportunity_lifecycle import (
    LifecycleReason,
    OpportunityLifecycleObservation,
    OpportunityLifecyclePolicy,
    OpportunityStage,
    audit_opportunity_lifecycle,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    current_price: float = 95.0,
    max_chase_price: float | None = 103.0,
) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation = 90.0
        target = 110.0
    else:
        invalidation = 110.0
        target = 90.0

    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=current_price,
            distance_from_current=abs(100.0 - current_price),
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.MARKET_NEAR,
            rationale=("fixture entry",),
            max_chase_price=max_chase_price,
            expires_after_seconds=600,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("fixture invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target,
                    label="tp1",
                    rationale=("fixture target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=1.0,
            structure_quality=1.0,
            entry_quality=1.0,
            momentum_quality=1.0,
            volume_quality=1.0,
            liquidity_quality=1.0,
            target_space_quality=1.0,
        ),
        evidence=StrategyEvidence(supporting=("fixture evidence",)),
        metadata={},
        lifecycle=CandidateLifecycle(
            cooldown_key="fixture",
            expires_after_seconds=600,
            expires_after_bars=6,
            invalidation_price=invalidation,
        ),
    )


def _audit(
    candidate: TradeCandidate,
    *,
    price: float,
    seconds: int = 0,
    bars: int = 0,
    previous_stage: OpportunityStage | None = None,
):
    return audit_opportunity_lifecycle(
        candidate,
        OpportunityLifecycleObservation(
            current_price=price,
            elapsed_seconds=seconds,
            elapsed_bars=bars,
        ),
        policy=OpportunityLifecyclePolicy(
            approaching_distance=3.0,
            armed_distance=1.0,
        ),
        previous_stage=previous_stage,
    )


def test_price_inside_entry_zone_is_cmp() -> None:
    audit = _audit(_candidate(), price=100.0)

    assert audit.stage is OpportunityStage.CMP
    assert audit.reasons == (LifecycleReason.PRICE_INSIDE_ENTRY_ZONE,)
    assert audit.distance_to_zone == 0.0
    assert audit.terminal is False


def test_nearby_price_is_armed() -> None:
    audit = _audit(_candidate(), price=98.5)

    assert audit.stage is OpportunityStage.ARMED
    assert audit.reasons == (LifecycleReason.PRICE_REACHED_TRIGGER,)
    assert audit.distance_to_zone == 0.5


def test_distant_price_is_developing() -> None:
    audit = _audit(_candidate(), price=94.0)

    assert audit.stage is OpportunityStage.DEVELOPING
    assert audit.reasons == (LifecycleReason.PRICE_APPROACHING_ENTRY,)
    assert audit.distance_to_zone == 5.0


def test_long_past_max_chase_is_missed() -> None:
    audit = _audit(_candidate(), price=104.0)

    assert audit.stage is OpportunityStage.MISSED
    assert audit.reasons == (LifecycleReason.PRICE_PASSED_MAX_CHASE,)
    assert audit.terminal is True


def test_short_past_max_chase_is_missed() -> None:
    candidate = _candidate(
        direction=TradeDirection.SHORT,
        current_price=105.0,
        max_chase_price=97.0,
    )

    audit = _audit(candidate, price=96.0)

    assert audit.stage is OpportunityStage.MISSED


def test_invalidation_has_precedence_over_expiry_and_missed() -> None:
    candidate = _candidate()

    audit = _audit(candidate, price=89.0, seconds=900, bars=10)

    assert audit.stage is OpportunityStage.INVALIDATED
    assert audit.reasons == (LifecycleReason.STRUCTURE_INVALIDATED,)


def test_time_expiry_has_precedence_over_missed() -> None:
    audit = _audit(_candidate(), price=104.0, seconds=600)

    assert audit.stage is OpportunityStage.EXPIRED
    assert audit.reasons == (LifecycleReason.TIME_BUDGET_EXHAUSTED,)


def test_bar_expiry_is_reported() -> None:
    audit = _audit(_candidate(), price=98.5, bars=6)

    assert audit.stage is OpportunityStage.EXPIRED
    assert audit.reasons == (LifecycleReason.BAR_BUDGET_EXHAUSTED,)


def test_previous_stage_is_preserved_for_transition_diagnostics() -> None:
    audit = _audit(
        _candidate(),
        price=100.0,
        previous_stage=OpportunityStage.ARMED,
    )

    assert audit.previous_stage is OpportunityStage.ARMED
    assert audit.stage is OpportunityStage.CMP


def test_policy_and_observation_reject_invalid_inputs() -> None:
    with pytest.raises(
        ValueError,
        match="armed distance cannot exceed approaching distance",
    ):
        OpportunityLifecyclePolicy(
            approaching_distance=1.0,
            armed_distance=2.0,
        )

    with pytest.raises(
        ValueError,
        match="elapsed seconds cannot be negative",
    ):
        OpportunityLifecycleObservation(
            current_price=100.0,
            elapsed_seconds=-1,
            elapsed_bars=0,
        )


def test_lifecycle_audit_does_not_mutate_candidate() -> None:
    candidate = _candidate()
    original_entry = candidate.entry
    original_lifecycle = candidate.lifecycle
    original_metadata = candidate.metadata

    audit_opportunity_lifecycle(
        candidate,
        OpportunityLifecycleObservation(
            current_price=100.0,
            elapsed_seconds=0,
            elapsed_bars=0,
        ),
        policy=OpportunityLifecyclePolicy(
            approaching_distance=3.0,
            armed_distance=1.0,
        ),
    )

    assert candidate.entry is original_entry
    assert candidate.lifecycle is original_lifecycle
    assert candidate.metadata is original_metadata
