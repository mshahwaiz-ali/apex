from __future__ import annotations

from datetime import UTC, datetime

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
from apex.strategies.opportunity_collision import (
    CollisionKind,
    CollisionResolution,
    CollisionResolutionPolicy,
    OpportunitySequencePolicy,
    SequenceDisposition,
)
from apex.strategies.opportunity_composition import (
    OpportunityCompositionPolicy,
    TransitionDisposition,
    TransitionReason,
    audit_opportunity_composition,
    audit_opportunity_transition,
)
from apex.strategies.opportunity_lifecycle import (
    OpportunityLifecycleObservation,
    OpportunityLifecyclePolicy,
    OpportunityStage,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    *,
    direction: TradeDirection,
    entry_lower: float,
    entry_upper: float,
    current_price: float,
    invalidation_price: float,
    target_price: float,
    strategy: StrategyType,
    evidence: str,
    max_chase_price: float,
) -> TradeCandidate:
    preferred = (entry_lower + entry_upper) / 2
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=strategy,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_lower,
            upper=entry_upper,
            preferred=preferred,
            current_price=current_price,
            distance_from_current=abs(preferred - current_price),
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
            price=invalidation_price,
            rationale=("fixture invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target_price,
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
        evidence=StrategyEvidence(supporting=(evidence,)),
        metadata={},
        lifecycle=CandidateLifecycle(
            cooldown_key=f"{direction.value}:{strategy.value}",
            expires_after_seconds=600,
            expires_after_bars=6,
            invalidation_price=invalidation_price,
        ),
    )


def _policy() -> OpportunityCompositionPolicy:
    return OpportunityCompositionPolicy(
        collision=CollisionResolutionPolicy(minimum_advantage=0.05),
        sequence=OpportunitySequencePolicy(minimum_zone_gap=1.0),
        lifecycle=OpportunityLifecyclePolicy(
            approaching_distance=3.0,
            armed_distance=1.0,
        ),
    )


def _observation(
    price: float,
    *,
    seconds: int = 0,
    bars: int = 0,
) -> OpportunityLifecycleObservation:
    return OpportunityLifecycleObservation(
        current_price=price,
        elapsed_seconds=seconds,
        elapsed_bars=bars,
    )


def test_composition_reports_unresolved_cmp_collision_without_suppression() -> None:
    long_candidate = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=95.0,
        target_price=110.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="long evidence",
        max_chase_price=103.0,
    )
    short_candidate = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=100.0,
        entry_upper=102.0,
        current_price=100.0,
        invalidation_price=106.0,
        target_price=92.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="short evidence",
        max_chase_price=98.0,
    )

    audit = audit_opportunity_composition(
        long_candidate,
        short_candidate,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_policy(),
    )

    assert audit.collision.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP
    assert audit.resolution.resolution is CollisionResolution.NEUTRAL
    assert audit.sequence.disposition is SequenceDisposition.UNRESOLVED_COLLISION
    assert audit.current_lifecycle.stage is OpportunityStage.CMP
    assert audit.follow_up_lifecycle.stage is OpportunityStage.CMP
    assert audit.transitions_legal is True


def test_composition_reports_valid_sequential_opposite_setups() -> None:
    current_short = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=106.0,
        target_price=92.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="current short evidence",
        max_chase_price=97.0,
    )
    lower_long = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=90.0,
        entry_upper=92.0,
        current_price=100.0,
        invalidation_price=86.0,
        target_price=102.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="follow-up sweep evidence",
        max_chase_price=None,
    )

    audit = audit_opportunity_composition(
        current_short,
        lower_long,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_policy(),
        current_previous_stage=OpportunityStage.ARMED,
        follow_up_previous_stage=OpportunityStage.DEVELOPING,
    )

    assert audit.collision.kind is CollisionKind.NONE
    assert audit.resolution.resolution is CollisionResolution.NOT_APPLICABLE
    assert audit.sequence.disposition is SequenceDisposition.VALID_SEQUENCE
    assert audit.current_lifecycle.stage is OpportunityStage.CMP
    assert audit.follow_up_lifecycle.stage is OpportunityStage.DEVELOPING
    assert audit.current_transition.reason is TransitionReason.ACTIVE_STAGE_MOVEMENT
    assert audit.follow_up_transition.reason is TransitionReason.SAME_STAGE


def test_terminal_stage_cannot_return_to_active_stage() -> None:
    transition = audit_opportunity_transition(
        OpportunityStage.MISSED,
        OpportunityStage.ARMED,
    )

    assert transition.disposition is TransitionDisposition.ILLEGAL
    assert transition.reason is TransitionReason.TERMINAL_REACTIVATION_BLOCKED
    assert transition.legal is False


def test_invalidated_stage_cannot_change_to_other_terminal_stage() -> None:
    transition = audit_opportunity_transition(
        OpportunityStage.INVALIDATED,
        OpportunityStage.EXPIRED,
    )

    assert transition.disposition is TransitionDisposition.ILLEGAL
    assert transition.reason is TransitionReason.INVALIDATED_STATE_CHANGED


def test_terminal_stage_may_advance_to_invalidation() -> None:
    transition = audit_opportunity_transition(
        OpportunityStage.MISSED,
        OpportunityStage.INVALIDATED,
    )

    assert transition.disposition is TransitionDisposition.LEGAL
    assert transition.reason is TransitionReason.TERMINAL_PRECEDENCE_ADVANCED


def test_composition_flags_illegal_terminal_reactivation() -> None:
    current_long = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=95.0,
        target_price=110.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="current long evidence",
        max_chase_price=103.0,
    )
    upper_short = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=108.0,
        entry_upper=110.0,
        current_price=100.0,
        invalidation_price=114.0,
        target_price=98.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="upper reversal evidence",
        max_chase_price=106.0,
    )

    audit = audit_opportunity_composition(
        current_long,
        upper_short,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(107.5),
        policy=_policy(),
        current_previous_stage=OpportunityStage.MISSED,
        follow_up_previous_stage=OpportunityStage.DEVELOPING,
    )

    assert audit.current_lifecycle.stage is OpportunityStage.CMP
    assert audit.current_transition.disposition is TransitionDisposition.ILLEGAL
    assert audit.transitions_legal is False


def test_composition_does_not_mutate_candidates() -> None:
    current_short = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=106.0,
        target_price=92.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="current short evidence",
        max_chase_price=97.0,
    )
    lower_long = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=90.0,
        entry_upper=92.0,
        current_price=100.0,
        invalidation_price=86.0,
        target_price=102.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="follow-up sweep evidence",
        max_chase_price=94.0,
    )
    current_entry = current_short.entry
    current_lifecycle = current_short.lifecycle
    follow_up_entry = lower_long.entry
    follow_up_lifecycle = lower_long.lifecycle

    audit_opportunity_composition(
        current_short,
        lower_long,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_policy(),
    )

    assert current_short.entry is current_entry
    assert current_short.lifecycle is current_lifecycle
    assert lower_long.entry is follow_up_entry
    assert lower_long.lifecycle is follow_up_lifecycle
