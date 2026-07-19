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
from apex.strategies.opportunity_collision import (
    OpportunitySequencePolicy,
    SequenceDisposition,
    SequenceReason,
    audit_opportunity_sequence,
)
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    *,
    direction: TradeDirection,
    lower: float,
    upper: float,
    preferred: float,
    invalidation: float,
    strategy: StrategyType,
    evidence: str,
    symbol: str = "BTCUSDT",
    current_price: float = 100.0,
) -> TradeCandidate:
    target = upper + 5.0 if direction is TradeDirection.LONG else lower - 5.0
    return TradeCandidate(
        symbol=symbol,
        strategy=strategy,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=lower,
            upper=upper,
            preferred=preferred,
            current_price=current_price,
            distance_from_current=abs(preferred - current_price),
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
        evidence=StrategyEvidence(
            supporting=(evidence,),
            structure_references=(strategy.value,),
        ),
        metadata={},
    )


def test_current_short_followed_by_lower_long_is_valid_sequence() -> None:
    current = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=103.0,
        strategy=StrategyType.MOMENTUM_SCALP,
        evidence="current rejection",
    )
    follow_up = _candidate(
        direction=TradeDirection.LONG,
        lower=90.0,
        upper=92.0,
        preferred=91.0,
        invalidation=87.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="lower sweep recovery",
    )

    audit = audit_opportunity_sequence(
        current,
        follow_up,
        policy=OpportunitySequencePolicy(minimum_zone_gap=2.0),
    )

    assert audit.disposition is SequenceDisposition.VALID_SEQUENCE
    assert audit.can_coexist is True
    assert audit.reasons == ()
    assert audit.zone_gap == 7.0
    assert audit.current_executable is True
    assert audit.follow_up_executable is False
    assert audit.independent_invalidation is True
    assert audit.independent_evidence is True


def test_same_zone_opposite_setups_are_unresolved_collision() -> None:
    current = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=97.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="breakout",
    )
    opposite = _candidate(
        direction=TradeDirection.SHORT,
        lower=100.0,
        upper=102.0,
        preferred=101.0,
        invalidation=104.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="rejection",
    )

    audit = audit_opportunity_sequence(
        current,
        opposite,
        policy=OpportunitySequencePolicy(),
    )

    assert audit.disposition is SequenceDisposition.UNRESOLVED_COLLISION
    assert SequenceReason.ENTRY_ZONES_OVERLAP in audit.reasons
    assert audit.can_coexist is False


def test_mirrored_duplicate_without_independent_thesis_is_rejected() -> None:
    current = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=103.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="same thesis",
    )
    follow_up = _candidate(
        direction=TradeDirection.LONG,
        lower=90.0,
        upper=92.0,
        preferred=91.0,
        invalidation=87.0,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        evidence="same thesis",
    )

    audit = audit_opportunity_sequence(
        current,
        follow_up,
        policy=OpportunitySequencePolicy(),
    )

    assert audit.disposition is SequenceDisposition.DUPLICATE_THESIS
    assert SequenceReason.SHARED_INVALIDATION not in audit.reasons
    assert SequenceReason.INSUFFICIENT_INDEPENDENT_EVIDENCE in audit.reasons


def test_follow_up_already_at_cmp_is_invalid_order() -> None:
    current = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=103.0,
        strategy=StrategyType.MOMENTUM_SCALP,
        evidence="current rejection",
    )
    follow_up = _candidate(
        direction=TradeDirection.LONG,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=97.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="reclaim",
    )

    audit = audit_opportunity_sequence(
        current,
        follow_up,
        policy=OpportunitySequencePolicy(),
    )

    assert audit.disposition is SequenceDisposition.UNRESOLVED_COLLISION
    assert SequenceReason.FOLLOW_UP_ALREADY_EXECUTABLE in audit.reasons


def test_wrong_side_follow_up_is_invalid_order() -> None:
    current = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=103.0,
        strategy=StrategyType.MOMENTUM_SCALP,
        evidence="current rejection",
    )
    follow_up = _candidate(
        direction=TradeDirection.LONG,
        lower=108.0,
        upper=110.0,
        preferred=109.0,
        invalidation=105.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="upper recovery",
    )

    audit = audit_opportunity_sequence(
        current,
        follow_up,
        policy=OpportunitySequencePolicy(),
    )

    assert audit.disposition is SequenceDisposition.INVALID_ORDER
    assert SequenceReason.FOLLOW_UP_NOT_DIRECTIONALLY_SEPARATED in audit.reasons


def test_sequence_policy_rejects_negative_gap() -> None:
    with pytest.raises(
        ValueError,
        match="minimum zone gap cannot be negative",
    ):
        OpportunitySequencePolicy(minimum_zone_gap=-0.1)


def test_sequence_audit_does_not_mutate_candidates() -> None:
    current = _candidate(
        direction=TradeDirection.SHORT,
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        invalidation=103.0,
        strategy=StrategyType.MOMENTUM_SCALP,
        evidence="current rejection",
    )
    follow_up = _candidate(
        direction=TradeDirection.LONG,
        lower=90.0,
        upper=92.0,
        preferred=91.0,
        invalidation=87.0,
        strategy=StrategyType.RANGE_REVERSAL,
        evidence="lower sweep recovery",
    )
    current_entry = current.entry
    follow_up_entry = follow_up.entry
    current_evidence = current.evidence
    follow_up_evidence = follow_up.evidence

    audit_opportunity_sequence(
        current,
        follow_up,
        policy=OpportunitySequencePolicy(),
    )

    assert current.entry is current_entry
    assert follow_up.entry is follow_up_entry
    assert current.evidence is current_evidence
    assert follow_up.evidence is follow_up_evidence
