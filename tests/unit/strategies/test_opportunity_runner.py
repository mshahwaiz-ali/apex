from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.contracts import (
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
from apex.strategies.opportunity_runner import (
    RunnerDecision,
    RunnerObservation,
    RunnerReason,
    audit_runner_lifecycle,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    direction: TradeDirection = TradeDirection.LONG,
) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation = 95.0
        target = 110.0
    else:
        invalidation = 105.0
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
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=1.0,
            mode=EntryMode.MARKET_NEAR,
            rationale=("fixture entry",),
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
    )


def _healthy_observation(
    *,
    protect_reference: float | None = None,
) -> RunnerObservation:
    return RunnerObservation(
        structure_intact_3m=True,
        structure_intact_5m=True,
        opposite_reclaim=False,
        continuation_volume_healthy=True,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
        protect_reference=protect_reference,
    )


def test_runner_hold_when_structure_and_continuation_remain_healthy() -> None:
    audit = audit_runner_lifecycle(
        _candidate(),
        _healthy_observation(),
    )

    assert audit.decision is RunnerDecision.HOLD_RUNNER
    assert audit.reasons == (
        RunnerReason.STRUCTURE_INTACT,
        RunnerReason.CONTINUATION_HEALTHY,
        RunnerReason.TARGET_ROOM_AVAILABLE,
    )
    assert audit.requires_exit is False
    assert audit.requires_tightening is False


def test_runner_tightens_when_momentum_slows_but_thesis_remains_intact() -> None:
    observation = RunnerObservation(
        structure_intact_3m=True,
        structure_intact_5m=True,
        opposite_reclaim=False,
        continuation_volume_healthy=True,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
        momentum_slowing=True,
        protect_reference=102.5,
    )

    audit = audit_runner_lifecycle(_candidate(), observation)

    assert audit.decision is RunnerDecision.TIGHTEN_AND_HOLD
    assert audit.reasons == (RunnerReason.MOMENTUM_SLOWING,)
    assert audit.protect_reference == 102.5
    assert audit.requires_tightening is True


def test_runner_tightens_for_mixed_flow_and_nearby_opposition() -> None:
    observation = RunnerObservation(
        structure_intact_3m=True,
        structure_intact_5m=True,
        opposite_reclaim=False,
        continuation_volume_healthy=True,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
        opposing_structure_near=True,
        flow_mixed=True,
        protect_reference=103.0,
    )

    audit = audit_runner_lifecycle(_candidate(), observation)

    assert audit.decision is RunnerDecision.TIGHTEN_AND_HOLD
    assert audit.reasons == (
        RunnerReason.OPPOSING_STRUCTURE_NEAR,
        RunnerReason.FLOW_MIXED,
    )


def test_runner_exits_on_opposite_reclaim() -> None:
    observation = RunnerObservation(
        structure_intact_3m=True,
        structure_intact_5m=True,
        opposite_reclaim=True,
        continuation_volume_healthy=True,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
    )

    audit = audit_runner_lifecycle(_candidate(), observation)

    assert audit.decision is RunnerDecision.EXIT_REMAINDER
    assert audit.reasons == (RunnerReason.OPPOSITE_RECLAIM,)
    assert audit.requires_exit is True
    assert audit.protect_reference is None


def test_runner_exit_has_precedence_over_tightening() -> None:
    observation = RunnerObservation(
        structure_intact_3m=False,
        structure_intact_5m=True,
        opposite_reclaim=False,
        continuation_volume_healthy=False,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
        momentum_slowing=True,
        protect_reference=102.0,
    )

    audit = audit_runner_lifecycle(_candidate(), observation)

    assert audit.decision is RunnerDecision.EXIT_REMAINDER
    assert audit.reasons == (RunnerReason.STRUCTURE_BROKEN_3M,)


def test_runner_exit_collects_all_terminal_reasons_deterministically() -> None:
    observation = RunnerObservation(
        structure_intact_3m=False,
        structure_intact_5m=False,
        opposite_reclaim=True,
        continuation_volume_healthy=False,
        correct_side_vwap_or_ema=False,
        target_room_remaining=False,
        strong_opposing_absorption=True,
        thesis_intact_15m=False,
        momentum_reversal_confirmed=True,
        stagnation_expired=True,
    )

    audit = audit_runner_lifecycle(_candidate(), observation)

    assert audit.reasons == (
        RunnerReason.STRUCTURE_BROKEN_3M,
        RunnerReason.STRUCTURE_BROKEN_5M,
        RunnerReason.OPPOSITE_RECLAIM,
        RunnerReason.MOMENTUM_REVERSAL_CONFIRMED,
        RunnerReason.STAGNATION_EXPIRED,
        RunnerReason.THESIS_BROKEN_15M,
        RunnerReason.STRONG_OPPOSING_ABSORPTION,
    )


def test_tighten_requires_explicit_protect_reference() -> None:
    observation = RunnerObservation(
        structure_intact_3m=True,
        structure_intact_5m=True,
        opposite_reclaim=False,
        continuation_volume_healthy=True,
        correct_side_vwap_or_ema=True,
        target_room_remaining=True,
        strong_opposing_absorption=False,
        thesis_intact_15m=True,
        momentum_slowing=True,
    )

    with pytest.raises(
        ValueError,
        match="tighten-and-hold decision requires a protect reference",
    ):
        audit_runner_lifecycle(_candidate(), observation)


def test_observation_rejects_invalid_protect_reference() -> None:
    with pytest.raises(
        ValueError,
        match="protect reference must be positive and finite",
    ):
        _healthy_observation(protect_reference=0.0)


def test_runner_audit_preserves_candidate_immutability() -> None:
    candidate = _candidate(TradeDirection.SHORT)
    original_entry = candidate.entry
    original_lifecycle = candidate.lifecycle
    original_metadata = candidate.metadata

    audit_runner_lifecycle(
        candidate,
        _healthy_observation(protect_reference=97.5),
    )

    assert candidate.entry is original_entry
    assert candidate.lifecycle is original_lifecycle
    assert candidate.metadata is original_metadata
