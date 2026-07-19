from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    exhaustion_reversal_archetype_profile,
)
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
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _candidate(
    *,
    direction: TradeDirection = TradeDirection.LONG,
    rsi: float | None = 30.0,
    include_rsi_evidence: bool = True,
    include_liquidity_trigger: bool = True,
    include_rsi_reference: bool = True,
    include_liquidity_reference: bool = True,
    provisional: bool = False,
) -> TradeCandidate:
    entry = EntryZone(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.0,
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=0.9,
        mode=EntryMode.SWEEP_RECOVERY,
        rationale=("liquidity rejection recovery entry",),
        max_chase_price=102.0 if direction is TradeDirection.LONG else 98.0,
    )
    supporting = tuple(
        item
        for item, present in (
            (
                f"RSI exhaustion is confirmed at {rsi:.2f}"
                if rsi is not None
                else "RSI exhaustion metadata is unavailable",
                include_rsi_evidence,
            ),
            (
                "liquidity rejection provides the reversal trigger",
                include_liquidity_trigger,
            ),
        )
        if present
    )
    invalidation_price = 97.0 if direction is TradeDirection.LONG else 103.0
    target_price = 106.0 if direction is TradeDirection.LONG else 94.0

    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.EXHAUSTION_REVERSAL,
        direction=direction,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.LIQUIDITY,
            price=invalidation_price,
            rationale=("rejection thesis fails beyond the liquidity extreme",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.LIQUIDITY,
                    price=target_price,
                    label="primary",
                    rationale=("opposite liquidity objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.4,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.8,
            volume_quality=0.7,
            liquidity_quality=0.9,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting or ("liquidity reversal geometry remains visible",),
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=(
                ("rate_of_change", "rsi") if include_rsi_reference else ("rate_of_change",)
            ),
            structure_references=("liquidity_rejection",),
            liquidity_references=(("swept_boundary",) if include_liquidity_reference else ()),
        ),
        metadata={
            "strategy_family": StrategyType.EXHAUSTION_REVERSAL.value,
            "source_strategy": StrategyType.LIQUIDITY_REJECTION_REVERSAL.value,
            "exhaustion_rsi": rsi,
        },
        entry_opportunities=(entry,),
        provisional=provisional,
    )


@pytest.mark.parametrize(
    ("direction", "rsi"),
    (
        (TradeDirection.LONG, 35.0),
        (TradeDirection.SHORT, 65.0),
    ),
)
def test_directional_exhaustion_maps_to_common_contract(
    direction: TradeDirection,
    rsi: float,
) -> None:
    profile = exhaustion_reversal_archetype_profile(_candidate(direction=direction, rsi=rsi))

    assert profile.archetype is ArchetypeFamily.EXHAUSTION_REVERSAL
    assert profile.strategy is StrategyType.EXHAUSTION_REVERSAL
    assert profile.entry_modes == (EntryMode.SWEEP_RECOVERY,)
    assert profile.invalidation_type is InvalidationType.LIQUIDITY
    assert profile.target_types == (TargetType.LIQUIDITY,)
    assert profile.regime_eligible is True
    assert profile.confirmation_complete is True
    assert f"RSI {rsi:.2f}" in profile.explanation_labels


def test_profile_preserves_lineage_and_existing_optional_evidence() -> None:
    profile = exhaustion_reversal_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit exhaustion-reversal family metadata",
        "structure evidence",
        "additional momentum evidence",
    )


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(rsi=None),
        _candidate(rsi=50.0),
        _candidate(include_rsi_evidence=False),
        _candidate(include_liquidity_trigger=False),
        _candidate(include_rsi_reference=False),
        _candidate(include_liquidity_reference=False),
    ),
)
def test_eligibility_requires_existing_generator_facts(
    candidate: TradeCandidate,
) -> None:
    profile = exhaustion_reversal_archetype_profile(candidate)

    assert profile.regime_eligible is False
    assert profile.confirmation_complete is False


def test_short_candidate_rejects_long_side_rsi_exhaustion() -> None:
    profile = exhaustion_reversal_archetype_profile(
        _candidate(direction=TradeDirection.SHORT, rsi=30.0)
    )

    assert profile.regime_eligible is False


def test_provisional_state_is_visible_without_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)

    profile = exhaustion_reversal_archetype_profile(candidate)

    assert profile.regime_eligible is True
    assert profile.confirmation_complete is False
    assert profile.provisional is True
    assert profile.contradictions == ("active-candle evidence is provisional",)
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata


def test_wrong_strategy_is_rejected() -> None:
    candidate = _candidate()
    wrong = TradeCandidate(
        symbol=candidate.symbol,
        strategy=StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        direction=candidate.direction,
        decision_time=candidate.decision_time,
        entry=candidate.entry,
        invalidation=candidate.invalidation,
        targets=candidate.targets,
        quality=candidate.quality,
        evidence=candidate.evidence,
        metadata=candidate.metadata,
        entry_opportunities=candidate.entry_opportunities,
        provisional=candidate.provisional,
    )

    with pytest.raises(
        ValueError,
        match="exhaustion-reversal profile requires an exhaustion-reversal candidate",
    ):
        exhaustion_reversal_archetype_profile(wrong)
