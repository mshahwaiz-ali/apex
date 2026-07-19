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


def test_long_execution_stop_is_beyond_structural_invalidation() -> None:
    from apex.strategies.geometry_audit import derive_execution_stop_geometry

    geometry = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=1.5,
    )

    assert geometry.executable_stop == 93.5
    assert geometry.structural_risk_distance == 5.0
    assert geometry.executable_risk_distance == 6.5


def test_short_execution_stop_is_beyond_structural_invalidation() -> None:
    from apex.strategies.geometry_audit import derive_execution_stop_geometry

    geometry = derive_execution_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        structural_invalidation=105.0,
        execution_buffer=1.5,
    )

    assert geometry.executable_stop == 106.5
    assert geometry.structural_risk_distance == 5.0
    assert geometry.executable_risk_distance == 6.5


def test_zero_buffer_keeps_stop_at_structural_invalidation() -> None:
    from apex.strategies.geometry_audit import derive_execution_stop_geometry

    long_geometry = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=0.0,
    )
    short_geometry = derive_execution_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        structural_invalidation=105.0,
        execution_buffer=0.0,
    )

    assert long_geometry.executable_stop == 95.0
    assert short_geometry.executable_stop == 105.0


def test_execution_stop_rejects_negative_buffer() -> None:
    import pytest

    from apex.strategies.geometry_audit import derive_execution_stop_geometry

    with pytest.raises(ValueError, match="execution buffer cannot be negative"):
        derive_execution_stop_geometry(
            direction=TradeDirection.LONG,
            preferred_entry=100.0,
            structural_invalidation=95.0,
            execution_buffer=-0.01,
        )


def test_execution_stop_rejects_directionally_invalid_structure() -> None:
    import pytest

    from apex.strategies.geometry_audit import derive_execution_stop_geometry

    with pytest.raises(
        ValueError,
        match="long structural invalidation must be below preferred entry",
    ):
        derive_execution_stop_geometry(
            direction=TradeDirection.LONG,
            preferred_entry=100.0,
            structural_invalidation=101.0,
            execution_buffer=1.0,
        )

    with pytest.raises(
        ValueError,
        match="short structural invalidation must be above preferred entry",
    ):
        derive_execution_stop_geometry(
            direction=TradeDirection.SHORT,
            preferred_entry=100.0,
            structural_invalidation=99.0,
            execution_buffer=1.0,
        )


def test_execution_buffer_uses_larger_atr_component() -> None:
    from apex.strategies.geometry_audit import (
        ExecutionBufferPolicy,
        derive_execution_buffer,
    )

    decision = derive_execution_buffer(
        atr=2.0,
        spread=0.25,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
        ),
    )

    assert decision.atr_component == 1.0
    assert decision.spread_component == 0.5
    assert decision.unclamped_buffer == 1.0
    assert decision.execution_buffer == 1.0
    assert decision.floor_applied is False
    assert decision.cap_applied is False


def test_execution_buffer_uses_larger_spread_component() -> None:
    from apex.strategies.geometry_audit import (
        ExecutionBufferPolicy,
        derive_execution_buffer,
    )

    decision = derive_execution_buffer(
        atr=1.0,
        spread=0.4,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.25,
            spread_multiplier=2.0,
        ),
    )

    assert decision.atr_component == 0.25
    assert decision.spread_component == 0.8
    assert decision.execution_buffer == 0.8


def test_execution_buffer_applies_floor_and_cap() -> None:
    from apex.strategies.geometry_audit import (
        ExecutionBufferPolicy,
        derive_execution_buffer,
    )

    floored = derive_execution_buffer(
        atr=0.1,
        spread=0.01,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
            minimum_buffer=0.2,
            maximum_buffer=1.0,
        ),
    )
    capped = derive_execution_buffer(
        atr=10.0,
        spread=0.5,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
            minimum_buffer=0.2,
            maximum_buffer=1.0,
        ),
    )

    assert floored.execution_buffer == 0.2
    assert floored.floor_applied is True
    assert floored.cap_applied is False

    assert capped.execution_buffer == 1.0
    assert capped.floor_applied is False
    assert capped.cap_applied is True


def test_execution_buffer_rejects_invalid_policy_and_inputs() -> None:
    import pytest

    from apex.strategies.geometry_audit import (
        ExecutionBufferPolicy,
        derive_execution_buffer,
    )

    with pytest.raises(ValueError, match="ATR multiplier cannot be negative"):
        ExecutionBufferPolicy(
            atr_multiplier=-0.1,
            spread_multiplier=1.0,
        )

    with pytest.raises(
        ValueError,
        match="maximum buffer cannot be below minimum buffer",
    ):
        ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=1.0,
            minimum_buffer=1.0,
            maximum_buffer=0.5,
        )

    policy = ExecutionBufferPolicy(
        atr_multiplier=0.5,
        spread_multiplier=1.0,
    )
    with pytest.raises(ValueError, match="ATR cannot be negative"):
        derive_execution_buffer(atr=-1.0, spread=0.1, policy=policy)
    with pytest.raises(ValueError, match="spread cannot be negative"):
        derive_execution_buffer(atr=1.0, spread=-0.1, policy=policy)


def test_buffer_decision_feeds_execution_stop_without_mutation() -> None:
    from apex.strategies.geometry_audit import (
        ExecutionBufferPolicy,
        derive_execution_buffer,
        derive_execution_stop_geometry,
    )

    decision = derive_execution_buffer(
        atr=2.0,
        spread=0.2,
        policy=ExecutionBufferPolicy(
            atr_multiplier=0.5,
            spread_multiplier=2.0,
        ),
    )
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=decision.execution_buffer,
    )

    assert decision.execution_buffer == 1.0
    assert stop.executable_stop == 94.0
    assert stop.executable_risk_distance == 6.0


def test_targets_are_audited_against_executable_long_risk() -> None:
    from apex.strategies.geometry_audit import (
        audit_targets_against_executable_stop,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=1.0,
    )

    audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    assert audit.executable_stop == 94.0
    assert audit.executable_risk_distance == 6.0
    assert tuple(target.reward_distance for target in audit.targets) == (5.0, 10.0)
    assert tuple(target.executable_reward_to_risk for target in audit.targets) == (
        5.0 / 6.0,
        10.0 / 6.0,
    )
    assert audit.minimum_reward_to_risk == 5.0 / 6.0
    assert audit.maximum_reward_to_risk == 10.0 / 6.0


def test_targets_are_audited_against_executable_short_risk() -> None:
    from apex.strategies.geometry_audit import (
        audit_targets_against_executable_stop,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.SHORT)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        structural_invalidation=105.0,
        execution_buffer=1.0,
    )

    audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    assert audit.executable_stop == 106.0
    assert audit.executable_risk_distance == 6.0
    assert tuple(target.reward_distance for target in audit.targets) == (5.0, 10.0)
    assert tuple(target.executable_reward_to_risk for target in audit.targets) == (
        5.0 / 6.0,
        10.0 / 6.0,
    )


def test_executable_target_audit_preserves_target_identity() -> None:
    from apex.strategies.geometry_audit import (
        audit_targets_against_executable_stop,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=0.5,
    )

    audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    assert tuple(target.label for target in audit.targets) == ("tp1", "tp2")
    assert tuple(target.kind for target in audit.targets) == (
        TargetType.STRUCTURAL,
        TargetType.LIQUIDITY,
    )
    assert tuple(target.price for target in audit.targets) == (105.0, 110.0)


def test_executable_target_audit_rejects_mismatched_geometry() -> None:
    import pytest

    from apex.strategies.geometry_audit import (
        audit_targets_against_executable_stop,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)

    wrong_direction = derive_execution_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        structural_invalidation=105.0,
        execution_buffer=1.0,
    )
    with pytest.raises(
        ValueError,
        match="candidate and stop geometry directions must match",
    ):
        audit_targets_against_executable_stop(
            candidate=candidate,
            stop_geometry=wrong_direction,
        )

    wrong_entry = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=101.0,
        structural_invalidation=95.0,
        execution_buffer=1.0,
    )
    with pytest.raises(
        ValueError,
        match="candidate and stop geometry preferred entries must match",
    ):
        audit_targets_against_executable_stop(
            candidate=candidate,
            stop_geometry=wrong_entry,
        )

    wrong_structure = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=94.0,
        execution_buffer=1.0,
    )
    with pytest.raises(
        ValueError,
        match="candidate invalidation and stop geometry structure must match",
    ):
        audit_targets_against_executable_stop(
            candidate=candidate,
            stop_geometry=wrong_structure,
        )


def test_executable_target_audit_does_not_mutate_candidate() -> None:
    from apex.strategies.geometry_audit import (
        audit_targets_against_executable_stop,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    original_targets = candidate.targets
    original_entry = candidate.entry
    original_invalidation = candidate.invalidation

    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=1.0,
    )
    audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    assert candidate.targets is original_targets
    assert candidate.entry is original_entry
    assert candidate.invalidation is original_invalidation


def test_target_quality_classifies_rr_tiers_without_reordering() -> None:
    from apex.strategies.geometry_audit import (
        TargetQualityPolicy,
        TargetQualityTier,
        audit_targets_against_executable_stop,
        classify_target_quality,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=1.0,
    )
    executable_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    quality = classify_target_quality(
        target_audit=executable_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=1.0,
            strong_reward_to_risk=1.5,
        ),
    )

    assert tuple(item.label for item in quality.assessments) == ("tp1", "tp2")
    assert tuple(item.tier for item in quality.assessments) == (
        TargetQualityTier.BELOW_MINIMUM,
        TargetQualityTier.STRONG,
    )
    assert quality.has_acceptable_target is True
    assert quality.has_strong_target is True


def test_target_quality_preserves_target_type_flags() -> None:
    from apex.strategies.geometry_audit import (
        TargetQualityPolicy,
        audit_targets_against_executable_stop,
        classify_target_quality,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=0.0,
    )
    executable_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    quality = classify_target_quality(
        target_audit=executable_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=0.5,
            strong_reward_to_risk=2.0,
        ),
    )

    first, second = quality.assessments
    assert first.is_structural is True
    assert first.is_liquidity_based is False
    assert second.is_structural is False
    assert second.is_liquidity_based is True


def test_target_quality_can_report_no_acceptable_target() -> None:
    from apex.strategies.geometry_audit import (
        TargetQualityPolicy,
        TargetQualityTier,
        audit_targets_against_executable_stop,
        classify_target_quality,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.SHORT)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.SHORT,
        preferred_entry=100.0,
        structural_invalidation=105.0,
        execution_buffer=5.0,
    )
    executable_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )

    quality = classify_target_quality(
        target_audit=executable_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=1.1,
            strong_reward_to_risk=2.0,
        ),
    )

    assert all(item.tier is TargetQualityTier.BELOW_MINIMUM for item in quality.assessments)
    assert quality.has_acceptable_target is False
    assert quality.has_strong_target is False


def test_target_quality_policy_rejects_invalid_thresholds() -> None:
    import pytest

    from apex.strategies.geometry_audit import TargetQualityPolicy

    with pytest.raises(
        ValueError,
        match="minimum reward-to-risk must be positive",
    ):
        TargetQualityPolicy(
            minimum_reward_to_risk=0.0,
            strong_reward_to_risk=1.0,
        )

    with pytest.raises(
        ValueError,
        match=("strong reward-to-risk cannot be below minimum reward-to-risk"),
    ):
        TargetQualityPolicy(
            minimum_reward_to_risk=2.0,
            strong_reward_to_risk=1.0,
        )


def test_target_quality_classification_does_not_mutate_target_audit() -> None:
    from apex.strategies.geometry_audit import (
        TargetQualityPolicy,
        audit_targets_against_executable_stop,
        classify_target_quality,
        derive_execution_stop_geometry,
    )

    candidate = _candidate(TradeDirection.LONG)
    stop = derive_execution_stop_geometry(
        direction=TradeDirection.LONG,
        preferred_entry=100.0,
        structural_invalidation=95.0,
        execution_buffer=1.0,
    )
    executable_audit = audit_targets_against_executable_stop(
        candidate=candidate,
        stop_geometry=stop,
    )
    original_targets = executable_audit.targets

    classify_target_quality(
        target_audit=executable_audit,
        policy=TargetQualityPolicy(
            minimum_reward_to_risk=1.0,
            strong_reward_to_risk=2.0,
        ),
    )

    assert executable_audit.targets is original_targets
