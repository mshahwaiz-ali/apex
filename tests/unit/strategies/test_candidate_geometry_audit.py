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
from apex.strategies.geometry_audit import audit_candidate_geometry
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(direction: TradeDirection) -> TradeCandidate:
    if direction is TradeDirection.LONG:
        invalidation = 95.0
        targets = (
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=105.0,
                label="tp1",
                rationale=("first structure",),
            ),
            TargetLevel(
                kind=TargetType.LIQUIDITY,
                price=110.0,
                label="tp2",
                rationale=("next liquidity",),
            ),
        )
    else:
        invalidation = 105.0
        targets = (
            TargetLevel(
                kind=TargetType.STRUCTURAL,
                price=95.0,
                label="tp1",
                rationale=("first structure",),
            ),
            TargetLevel(
                kind=TargetType.LIQUIDITY,
                price=90.0,
                label="tp2",
                rationale=("next liquidity",),
            ),
        )

    entry = EntryZone(
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
    )
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        direction=direction,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("fixture invalidation",),
        ),
        targets=TargetConcept(levels=targets),
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


def test_long_geometry_is_projected_without_mutation() -> None:
    candidate = _candidate(TradeDirection.LONG)
    original_entry = candidate.entry
    original_invalidation = candidate.invalidation
    original_targets = candidate.targets

    audit = audit_candidate_geometry(candidate)

    assert audit.is_consistent is True
    assert audit.preferred_entry == 100.0
    assert audit.structural_invalidation == 95.0
    assert audit.risk_distance == 5.0
    assert tuple(target.reward_distance for target in audit.targets) == (5.0, 10.0)
    assert tuple(target.reward_to_risk for target in audit.targets) == (1.0, 2.0)
    assert candidate.entry is original_entry
    assert candidate.invalidation is original_invalidation
    assert candidate.targets is original_targets


def test_short_geometry_is_directionally_symmetric() -> None:
    audit = audit_candidate_geometry(_candidate(TradeDirection.SHORT))

    assert audit.is_consistent is True
    assert audit.structural_invalidation == 105.0
    assert audit.risk_distance == 5.0
    assert tuple(target.reward_distance for target in audit.targets) == (5.0, 10.0)
    assert tuple(target.reward_to_risk for target in audit.targets) == (1.0, 2.0)


def test_target_types_and_labels_are_preserved() -> None:
    audit = audit_candidate_geometry(_candidate(TradeDirection.LONG))

    assert tuple(target.label for target in audit.targets) == ("tp1", "tp2")
    assert tuple(target.kind for target in audit.targets) == (
        TargetType.STRUCTURAL,
        TargetType.LIQUIDITY,
    )


def test_audit_is_deterministic() -> None:
    candidate = _candidate(TradeDirection.LONG)

    assert audit_candidate_geometry(candidate) == audit_candidate_geometry(candidate)
