from __future__ import annotations

from datetime import UTC, datetime

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
from apex.strategies.opportunity_collision import (
    CollisionKind,
    audit_cmp_collision,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    *,
    direction: TradeDirection,
    lower: float,
    upper: float,
    preferred: float,
    symbol: str = "BTCUSDT",
) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation = lower - 2.0
        target = upper + 5.0
    else:
        invalidation = upper + 2.0
        target = lower - 5.0

    entry = EntryZone(
        lower=lower,
        upper=upper,
        preferred=preferred,
        current_price=100.0,
        distance_from_current=abs(preferred - 100.0),
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=1.0,
        mode=EntryMode.MARKET_NEAR,
        rationale=("fixture entry",),
    )
    return TradeCandidate(
        symbol=symbol,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=direction,
        decision_time=NOW,
        entry=entry,
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


def test_opposite_candidates_in_same_zone_are_unresolved_collision() -> None:
    long_candidate = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    short_candidate = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )

    audit = audit_cmp_collision(long_candidate, short_candidate)

    assert audit.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP
    assert audit.overlap.lower == 100.0
    assert audit.overlap.upper == 101.0
    assert audit.overlap.width == 1.0
    assert audit.overlap.overlap_ratio == 0.5
    assert audit.unresolved_opposite_collision is True


def test_same_direction_overlap_is_not_opposite_collision() -> None:
    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.LONG,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )

    audit = audit_cmp_collision(left, right)

    assert audit.kind is CollisionKind.SAME_DIRECTION_OVERLAP
    assert audit.unresolved_opposite_collision is False


def test_separated_opposite_zones_do_not_collide() -> None:
    short_candidate = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    lower_long = _candidate(
        direction=TradeDirection.LONG,
        lower=90.0,
        upper=92.0,
        preferred=91.0,
    )

    audit = audit_cmp_collision(short_candidate, lower_long)

    assert audit.kind is CollisionKind.NONE
    assert audit.overlap.overlaps is False
    assert audit.overlap.width == 0.0
    assert audit.unresolved_opposite_collision is False


def test_touching_zones_count_as_zero_width_overlap() -> None:
    left = _candidate(
        direction=TradeDirection.LONG,
        lower=98.0,
        upper=100.0,
        preferred=99.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )

    audit = audit_cmp_collision(left, right)

    assert audit.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP
    assert audit.overlap.lower == 100.0
    assert audit.overlap.upper == 100.0
    assert audit.overlap.width == 0.0
    assert audit.overlap.overlap_ratio == 0.0


def test_different_symbols_are_not_unresolved_same_market_collision() -> None:
    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        symbol="BTCUSDT",
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        symbol="ETHUSDT",
    )

    audit = audit_cmp_collision(left, right)

    assert audit.kind is CollisionKind.OPPOSITE_DIRECTION_OVERLAP
    assert audit.same_symbol is False
    assert audit.unresolved_opposite_collision is False


def test_collision_audit_does_not_mutate_candidates() -> None:
    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )
    left_entry = left.entry
    right_entry = right.entry
    left_metadata = left.metadata
    right_metadata = right.metadata

    audit_cmp_collision(left, right)

    assert left.entry is left_entry
    assert right.entry is right_entry
    assert left.metadata is left_metadata
    assert right.metadata is right_metadata


def test_collision_resolution_prefers_stronger_quality_and_evidence() -> None:
    from dataclasses import replace

    from apex.strategies.opportunity_collision import (
        CollisionResolution,
        CollisionResolutionPolicy,
        audit_collision_resolution,
    )

    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )
    stronger_left = replace(
        left,
        evidence=StrategyEvidence(
            supporting=("fixture evidence", "extra confirmation"),
            feature_references=("rsi",),
            structure_references=("breakout",),
        ),
    )

    audit = audit_collision_resolution(
        stronger_left,
        right,
        policy=CollisionResolutionPolicy(
            quality_weight=1.0,
            evidence_weight=0.5,
            contradiction_penalty_weight=1.0,
            minimum_advantage=0.1,
        ),
    )

    assert audit.resolution is CollisionResolution.LEFT
    assert audit.has_decisive_winner is True
    assert audit.left.total > audit.right.total


def test_collision_resolution_can_prefer_right_candidate() -> None:
    from dataclasses import replace

    from apex.strategies.opportunity_collision import (
        CollisionResolution,
        CollisionResolutionPolicy,
        audit_collision_resolution,
    )

    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )
    weaker_left = replace(
        left,
        evidence=StrategyEvidence(
            supporting=("fixture evidence",),
            contradictions=("momentum conflict",),
            warnings=("volume weak",),
        ),
    )

    audit = audit_collision_resolution(
        weaker_left,
        right,
        policy=CollisionResolutionPolicy(
            quality_weight=1.0,
            evidence_weight=0.0,
            contradiction_penalty_weight=1.0,
            minimum_advantage=0.1,
        ),
    )

    assert audit.resolution is CollisionResolution.RIGHT
    assert audit.has_decisive_winner is True


def test_collision_resolution_is_neutral_inside_margin() -> None:
    from apex.strategies.opportunity_collision import (
        CollisionResolution,
        CollisionResolutionPolicy,
        audit_collision_resolution,
    )

    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )

    audit = audit_collision_resolution(
        left,
        right,
        policy=CollisionResolutionPolicy(minimum_advantage=0.5),
    )

    assert audit.resolution is CollisionResolution.NEUTRAL
    assert audit.has_decisive_winner is False
    assert audit.advantage == 0.0


def test_collision_resolution_is_not_applicable_without_same_market_collision() -> None:
    from apex.strategies.opportunity_collision import (
        CollisionResolution,
        CollisionResolutionPolicy,
        audit_collision_resolution,
    )

    left = _candidate(
        direction=TradeDirection.LONG,
        lower=90.0,
        upper=92.0,
        preferred=91.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )

    audit = audit_collision_resolution(
        left,
        right,
        policy=CollisionResolutionPolicy(),
    )

    assert audit.resolution is CollisionResolution.NOT_APPLICABLE
    assert audit.has_decisive_winner is False


def test_collision_resolution_policy_rejects_invalid_values() -> None:
    import pytest

    from apex.strategies.opportunity_collision import CollisionResolutionPolicy

    with pytest.raises(ValueError, match="quality weight cannot be negative"):
        CollisionResolutionPolicy(quality_weight=-1.0)

    with pytest.raises(
        ValueError,
        match="minimum advantage cannot be negative",
    ):
        CollisionResolutionPolicy(minimum_advantage=-0.01)


def test_collision_resolution_does_not_mutate_candidates() -> None:
    from apex.strategies.opportunity_collision import (
        CollisionResolutionPolicy,
        audit_collision_resolution,
    )

    left = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
    )
    right = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
    )
    left_entry = left.entry
    right_entry = right.entry
    left_evidence = left.evidence
    right_evidence = right.evidence

    audit_collision_resolution(
        left,
        right,
        policy=CollisionResolutionPolicy(),
    )

    assert left.entry is left_entry
    assert right.entry is right_entry
    assert left.evidence is left_evidence
    assert right.evidence is right_evidence
