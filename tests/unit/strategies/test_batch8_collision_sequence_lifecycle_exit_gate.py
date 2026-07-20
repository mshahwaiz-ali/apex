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
)
from apex.strategies.opportunity_lifecycle import (
    OpportunityLifecycleObservation,
    OpportunityLifecyclePolicy,
    OpportunityStage,
)
from apex.strategies.opportunity_plan_comparison import (
    CurrentPlanObservation,
    PlanChangeKind,
    PlanComparisonStatus,
    audit_original_plan_comparison,
    snapshot_original_plan,
)
from apex.strategies.opportunity_runner import (
    RunnerDecision,
    RunnerObservation,
    audit_runner_lifecycle,
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
    target_prices: tuple[float, ...],
    strategy: StrategyType,
    evidence: tuple[str, ...],
    contradictions: tuple[str, ...] = (),
    max_chase_price: float | None = None,
) -> TradeCandidate:
    preferred = (entry_lower + entry_upper) / 2
    levels = tuple(
        TargetLevel(
            kind=TargetType.STRUCTURAL,
            price=price,
            label=f"tp{index}",
            rationale=("exit-gate target",),
        )
        for index, price in enumerate(target_prices, start=1)
    )
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
            rationale=("exit-gate entry",),
            max_chase_price=max_chase_price,
            expires_after_seconds=600,
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("exit-gate invalidation",),
        ),
        targets=TargetConcept(levels=levels),
        quality=RawQualityMetrics(
            trend_alignment=1.0,
            structure_quality=1.0,
            entry_quality=1.0,
            momentum_quality=1.0,
            volume_quality=1.0,
            liquidity_quality=1.0,
            target_space_quality=1.0,
        ),
        evidence=StrategyEvidence(
            supporting=evidence,
            contradictions=contradictions,
        ),
        metadata={},
        lifecycle=CandidateLifecycle(
            cooldown_key=(f"BTCUSDT:{strategy.value}:{direction.value}:{preferred}"),
            expires_after_seconds=600,
            expires_after_bars=6,
            invalidation_price=invalidation_price,
        ),
    )


def _composition_policy() -> OpportunityCompositionPolicy:
    return OpportunityCompositionPolicy(
        collision=CollisionResolutionPolicy(minimum_advantage=0.05),
        sequence=OpportunitySequencePolicy(minimum_zone_gap=1.0),
        lifecycle=OpportunityLifecyclePolicy(
            approaching_distance=3.0,
            armed_distance=1.0,
        ),
    )


def _observation(price: float) -> OpportunityLifecycleObservation:
    return OpportunityLifecycleObservation(
        current_price=price,
        elapsed_seconds=0,
        elapsed_bars=0,
    )


def test_batch8_exit_gate_explains_unresolved_cmp_collision_without_mutation() -> None:
    long_candidate = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=95.0,
        target_prices=(106.0, 110.0),
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence=("long acceptance",),
        max_chase_price=103.0,
    )
    short_candidate = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=100.0,
        entry_upper=102.0,
        current_price=100.0,
        invalidation_price=106.0,
        target_prices=(96.0, 92.0),
        strategy=StrategyType.RANGE_REVERSAL,
        evidence=("short rejection",),
        max_chase_price=98.0,
    )
    long_entry = long_candidate.entry
    short_entry = short_candidate.entry
    long_lifecycle = long_candidate.lifecycle
    short_lifecycle = short_candidate.lifecycle

    audit = audit_opportunity_composition(
        long_candidate,
        short_candidate,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_composition_policy(),
    )

    assert audit.collision.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP
    assert audit.resolution.resolution is CollisionResolution.NEUTRAL
    assert audit.sequence.disposition is SequenceDisposition.UNRESOLVED_COLLISION
    assert audit.current_lifecycle.stage is OpportunityStage.CMP
    assert audit.follow_up_lifecycle.stage is OpportunityStage.CMP
    assert audit.transitions_legal is True
    assert long_candidate.entry is long_entry
    assert short_candidate.entry is short_entry
    assert long_candidate.lifecycle is long_lifecycle
    assert short_candidate.lifecycle is short_lifecycle


def test_batch8_exit_gate_supports_sequence_runner_and_original_plan_progression() -> None:
    current_short = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=106.0,
        target_prices=(96.0, 92.0),
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence=("short continuation",),
        max_chase_price=97.0,
    )
    lower_long = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=90.0,
        entry_upper=92.0,
        current_price=100.0,
        invalidation_price=86.0,
        target_prices=(98.0, 102.0),
        strategy=StrategyType.RANGE_REVERSAL,
        evidence=("lower sweep recovery",),
    )

    composition = audit_opportunity_composition(
        current_short,
        lower_long,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_composition_policy(),
        current_previous_stage=OpportunityStage.ARMED,
        follow_up_previous_stage=OpportunityStage.DEVELOPING,
    )

    assert composition.collision.kind is CollisionKind.NONE
    assert composition.sequence.disposition is SequenceDisposition.VALID_SEQUENCE
    assert composition.current_transition.disposition is TransitionDisposition.LEGAL
    assert composition.follow_up_transition.disposition is TransitionDisposition.LEGAL

    original = snapshot_original_plan(
        current_short,
        lifecycle_stage=OpportunityStage.CMP,
    )
    runner = audit_runner_lifecycle(
        current_short,
        RunnerObservation(
            structure_intact_3m=True,
            structure_intact_5m=True,
            opposite_reclaim=False,
            continuation_volume_healthy=True,
            correct_side_vwap_or_ema=True,
            target_room_remaining=True,
            strong_opposing_absorption=False,
            thesis_intact_15m=True,
            momentum_slowing=True,
            protect_reference=98.0,
        ),
    )
    comparison = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.CMP,
            achieved_target_labels=("tp1",),
            evidence=current_short.evidence,
            runner=runner,
        ),
    )

    assert runner.decision is RunnerDecision.TIGHTEN_AND_HOLD
    assert runner.protect_reference == 98.0
    assert comparison.status is PlanComparisonStatus.PROGRESSED
    assert tuple(change.kind for change in comparison.changes) == (
        PlanChangeKind.TARGET_ACHIEVED,
        PlanChangeKind.RUNNER_TIGHTEN,
    )


def test_batch8_exit_gate_blocks_terminal_reactivation_and_reports_terminal_plan() -> None:
    candidate = _candidate(
        direction=TradeDirection.LONG,
        entry_lower=99.0,
        entry_upper=101.0,
        current_price=100.0,
        invalidation_price=95.0,
        target_prices=(105.0, 110.0),
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence=("original support",),
        max_chase_price=103.0,
    )
    follow_up = _candidate(
        direction=TradeDirection.SHORT,
        entry_lower=108.0,
        entry_upper=110.0,
        current_price=100.0,
        invalidation_price=114.0,
        target_prices=(102.0, 98.0),
        strategy=StrategyType.RANGE_REVERSAL,
        evidence=("upper reversal",),
    )

    composition = audit_opportunity_composition(
        candidate,
        follow_up,
        current_observation=_observation(100.0),
        follow_up_observation=_observation(100.0),
        policy=_composition_policy(),
        current_previous_stage=OpportunityStage.MISSED,
        follow_up_previous_stage=OpportunityStage.DEVELOPING,
    )

    assert composition.current_lifecycle.stage is OpportunityStage.CMP
    assert composition.current_transition.disposition is TransitionDisposition.ILLEGAL
    assert composition.current_transition.reason is TransitionReason.TERMINAL_REACTIVATION_BLOCKED
    assert composition.transitions_legal is False

    original = snapshot_original_plan(
        candidate,
        lifecycle_stage=OpportunityStage.CMP,
    )
    runner = audit_runner_lifecycle(
        candidate,
        RunnerObservation(
            structure_intact_3m=False,
            structure_intact_5m=True,
            opposite_reclaim=True,
            continuation_volume_healthy=False,
            correct_side_vwap_or_ema=False,
            target_room_remaining=False,
            strong_opposing_absorption=True,
            thesis_intact_15m=False,
            momentum_reversal_confirmed=True,
            stagnation_expired=True,
        ),
    )
    comparison = audit_original_plan_comparison(
        original,
        CurrentPlanObservation(
            lifecycle_stage=OpportunityStage.INVALIDATED,
            achieved_target_labels=("tp1",),
            evidence=StrategyEvidence(
                supporting=("original support",),
                contradictions=("structure failed",),
            ),
            runner=runner,
        ),
    )

    assert runner.decision is RunnerDecision.EXIT_REMAINDER
    assert comparison.status is PlanComparisonStatus.TERMINAL
    assert comparison.current_stage is OpportunityStage.INVALIDATED
    assert PlanChangeKind.CONTRADICTION_ADDED in {change.kind for change in comparison.changes}
    assert PlanChangeKind.RUNNER_EXIT in {change.kind for change in comparison.changes}
