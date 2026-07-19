from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    vwap_reclaim_rejection_archetype_profile,
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
    atr_distance: float = 0.8,
    extended: bool = False,
    include_vwap: bool = True,
    provisional: bool = False,
) -> TradeCandidate:
    entry = EntryZone(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.5,
        atr_distance=atr_distance,
        estimated_move_missed=0.0,
        location_quality=0.9,
        mode=EntryMode.PULLBACK,
        rationale=("VWAP reclaim entry",),
        is_extended=extended,
        max_chase_price=102.0,
    )
    feature_references = ("ema_fast", "vwap") if include_vwap else ("ema_fast",)
    supporting = (
        (
            "VWAP provides the active reclaim or rejection reference",
            "entry remains close enough to VWAP for actionable execution",
        )
        if include_vwap
        else ("pullback entry remains structurally valid",)
    )
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.VWAP_RECLAIM_REJECTION,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=97.0,
            rationale=("VWAP reclaim failed",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=106.0,
                    label="primary",
                    rationale=("next structural objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.7,
            volume_quality=0.6,
            liquidity_quality=0.6,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting,
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=feature_references,
            structure_references=("trend", "levels", "vwap_reclaim_rejection"),
            liquidity_references=("opposing_liquidity",),
        ),
        metadata={
            "strategy_family": StrategyType.VWAP_RECLAIM_REJECTION.value,
            "source_strategy": StrategyType.TREND_PULLBACK.value,
        },
        entry_opportunities=(entry,),
        provisional=provisional,
    )


def test_vwap_candidate_maps_to_common_archetype_contract() -> None:
    profile = vwap_reclaim_rejection_archetype_profile(_candidate())

    assert profile.archetype is ArchetypeFamily.VWAP_RECLAIM_REJECTION
    assert profile.strategy is StrategyType.VWAP_RECLAIM_REJECTION
    assert profile.entry_modes == (EntryMode.PULLBACK,)
    assert profile.invalidation_type is InvalidationType.STRUCTURAL
    assert profile.target_types == (TargetType.STRUCTURAL,)
    assert profile.confirmation_complete is True
    assert profile.regime_eligible is True


def test_vwap_profile_preserves_lineage_and_optional_evidence() -> None:
    profile = vwap_reclaim_rejection_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit VWAP family metadata",
        "EMA confluence",
        "liquidity evidence",
    )
    assert profile.explanation_labels == (
        "VWAP reclaim or rejection",
        "confirmation complete",
        "closed evidence",
    )


@pytest.mark.parametrize(
    ("candidate", "eligible"),
    (
        (_candidate(atr_distance=1.26), False),
        (_candidate(extended=True), False),
        (_candidate(include_vwap=False), False),
    ),
)
def test_vwap_eligibility_uses_existing_candidate_facts(
    candidate: TradeCandidate,
    eligible: bool,
) -> None:
    profile = vwap_reclaim_rejection_archetype_profile(candidate)

    assert profile.regime_eligible is eligible
    assert profile.confirmation_complete is eligible


def test_provisional_state_is_visible_without_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)

    profile = vwap_reclaim_rejection_archetype_profile(candidate)

    assert profile.confirmation_complete is False
    assert profile.regime_eligible is True
    assert profile.provisional is True
    assert profile.contradictions == ("active-candle evidence is provisional",)
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata


def test_non_vwap_candidate_is_rejected() -> None:
    candidate = _candidate()
    wrong = TradeCandidate(
        symbol=candidate.symbol,
        strategy=StrategyType.TREND_PULLBACK,
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
        match="VWAP profile requires a VWAP-reclaim-rejection candidate",
    ):
        vwap_reclaim_rejection_archetype_profile(wrong)
