from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    failed_breakout_archetype_profile,
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
    confirmed_failed_breakout: bool = True,
    include_rejection: bool = True,
    include_return_inside: bool = True,
    include_structure_reference: bool = True,
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
        rationale=("return inside the failed range boundary",),
        max_chase_price=102.0,
    )
    supporting = tuple(
        item
        for item, present in (
            (
                "failed breakout rejected beyond the range boundary",
                include_rejection,
            ),
            (
                "price returned into the prior range before entry selection",
                include_return_inside,
            ),
            (
                "confirmed false-break state supports rejection back into the range",
                confirmed_failed_breakout,
            ),
        )
        if present
    )
    structure_references = (
        ("range", "levels", "failed_breakout")
        if include_structure_reference
        else ("range", "levels")
    )

    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.FAILED_BREAKOUT_REVERSAL,
        direction=TradeDirection.SHORT,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=103.0,
            rationale=("failed-breakout boundary recovery invalidated",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=94.0,
                    label="primary",
                    rationale=("opposite range boundary",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.5,
            structure_quality=0.9,
            entry_quality=0.9,
            momentum_quality=0.7,
            volume_quality=0.6,
            liquidity_quality=0.7,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting or ("range reversal geometry remains present",),
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=("rate_of_change", "relative_volume"),
            structure_references=structure_references,
            liquidity_references=("range_boundary",),
        ),
        metadata={
            "strategy_family": StrategyType.FAILED_BREAKOUT_REVERSAL.value,
            "source_strategy": StrategyType.RANGE_REVERSAL.value,
            "confirmed_failed_breakout": confirmed_failed_breakout,
        },
        entry_opportunities=(entry,),
        provisional=provisional,
    )


def test_failed_breakout_maps_to_common_archetype_contract() -> None:
    profile = failed_breakout_archetype_profile(_candidate())

    assert profile.archetype is ArchetypeFamily.FAILED_BREAKOUT
    assert profile.strategy is StrategyType.FAILED_BREAKOUT_REVERSAL
    assert profile.entry_modes == (EntryMode.SWEEP_RECOVERY,)
    assert profile.invalidation_type is InvalidationType.STRUCTURAL
    assert profile.target_types == (TargetType.STRUCTURAL,)
    assert profile.confirmation_complete is True
    assert profile.regime_eligible is True


def test_failed_breakout_profile_preserves_lineage_and_optional_evidence() -> None:
    profile = failed_breakout_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit failed-breakout family metadata",
        "momentum evidence",
        "liquidity evidence",
    )
    assert profile.explanation_labels == (
        "failed breakout reversal",
        "confirmation complete",
        "closed evidence",
    )


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(confirmed_failed_breakout=False),
        _candidate(include_rejection=False),
        _candidate(include_return_inside=False),
        _candidate(include_structure_reference=False),
    ),
)
def test_failed_breakout_eligibility_requires_existing_generator_facts(
    candidate: TradeCandidate,
) -> None:
    profile = failed_breakout_archetype_profile(candidate)

    assert profile.regime_eligible is False
    assert profile.confirmation_complete is False


def test_provisional_state_is_visible_without_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)

    profile = failed_breakout_archetype_profile(candidate)

    assert profile.regime_eligible is True
    assert profile.confirmation_complete is False
    assert profile.provisional is True
    assert profile.contradictions == ("active-candle evidence is provisional",)
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata


def test_non_failed_breakout_candidate_is_rejected() -> None:
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
        match="failed-breakout profile requires a failed-breakout-reversal candidate",
    ):
        failed_breakout_archetype_profile(wrong)
