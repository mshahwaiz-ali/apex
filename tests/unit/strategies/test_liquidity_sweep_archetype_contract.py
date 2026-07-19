from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    liquidity_sweep_archetype_profile,
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
    include_sweep: bool = True,
    include_recovery: bool = True,
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
        rationale=("swept boundary recovery",),
        max_chase_price=102.0,
    )

    supporting = tuple(
        item
        for item, present in (
            (
                "confirmed liquidity sweep and trap rejection define the reversal",
                include_sweep,
            ),
            (
                "price recovered the swept boundary before entry selection",
                include_recovery,
            ),
        )
        if present
    )
    liquidity_references = (
        ("liquidity_rejection_reversal", "swept_boundary") if include_liquidity_reference else ()
    )

    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.LIQUIDITY_REJECTION_REVERSAL,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.LIQUIDITY,
            price=97.0,
            rationale=("recovery failed below swept liquidity",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.LIQUIDITY,
                    price=106.0,
                    label="primary",
                    rationale=("opposing liquidity objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.5,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.7,
            volume_quality=0.7,
            liquidity_quality=0.95,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting or ("reversal geometry remains present",),
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=("rate_of_change", "relative_volume"),
            structure_references=("levels", "sweep_recovery"),
            liquidity_references=liquidity_references,
        ),
        metadata={
            "strategy_family": StrategyType.LIQUIDITY_REJECTION_REVERSAL.value,
            "source_strategy": StrategyType.RANGE_REVERSAL.value,
        },
        entry_opportunities=(entry,),
        provisional=provisional,
    )


def test_liquidity_sweep_maps_to_common_archetype_contract() -> None:
    profile = liquidity_sweep_archetype_profile(_candidate())

    assert profile.archetype is ArchetypeFamily.LIQUIDITY_SWEEP
    assert profile.strategy is StrategyType.LIQUIDITY_REJECTION_REVERSAL
    assert profile.entry_modes == (EntryMode.SWEEP_RECOVERY,)
    assert profile.invalidation_type is InvalidationType.LIQUIDITY
    assert profile.target_types == (TargetType.LIQUIDITY,)
    assert profile.confirmation_complete is True
    assert profile.regime_eligible is True


def test_liquidity_profile_preserves_lineage_and_optional_evidence() -> None:
    profile = liquidity_sweep_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit liquidity-rejection family metadata",
        "structure evidence",
        "momentum evidence",
    )
    assert profile.explanation_labels == (
        "liquidity sweep reversal",
        "confirmation complete",
        "closed evidence",
    )


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(include_sweep=False),
        _candidate(include_recovery=False),
        _candidate(include_liquidity_reference=False),
    ),
)
def test_liquidity_eligibility_requires_existing_sweep_facts(
    candidate: TradeCandidate,
) -> None:
    profile = liquidity_sweep_archetype_profile(candidate)

    assert profile.regime_eligible is False
    assert profile.confirmation_complete is False


def test_provisional_state_is_visible_without_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)

    profile = liquidity_sweep_archetype_profile(candidate)

    assert profile.regime_eligible is True
    assert profile.confirmation_complete is False
    assert profile.provisional is True
    assert profile.contradictions == ("active-candle evidence is provisional",)
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata


def test_non_liquidity_rejection_candidate_is_rejected() -> None:
    candidate = _candidate()
    wrong = TradeCandidate(
        symbol=candidate.symbol,
        strategy=StrategyType.RANGE_REVERSAL,
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
        match=("liquidity-sweep profile requires a liquidity-rejection-reversal candidate"),
    ):
        liquidity_sweep_archetype_profile(wrong)
