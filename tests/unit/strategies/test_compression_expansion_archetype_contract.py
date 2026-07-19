from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    compression_expansion_archetype_profile,
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
    regime: str = "compression",
    include_regime_evidence: bool = True,
    include_release_evidence: bool = True,
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
        mode=EntryMode.MOMENTUM_CONTINUATION,
        rationale=("confirmed release from prior volatility state",),
        max_chase_price=102.0,
    )
    supporting = tuple(
        item
        for item, present in (
            (f"{regime} context supports directional expansion", include_regime_evidence),
            (
                "confirmed breakout provides release from the prior volatility state",
                include_release_evidence,
            ),
        )
        if present
    )
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.COMPRESSION_EXPANSION,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=97.0,
            rationale=("expansion failure below prior structure",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.EXPANSION,
                    price=106.0,
                    label="primary",
                    rationale=("expansion objective",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.7,
            structure_quality=0.9,
            entry_quality=0.9,
            momentum_quality=0.8,
            volume_quality=0.7,
            liquidity_quality=0.6,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting or ("breakout context remains visible",),
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=("relative_volume", "rate_of_change"),
            structure_references=(
                ("compression", "compression_expansion")
                if include_structure_reference
                else ("compression",)
            ),
            liquidity_references=("breakout_boundary",),
        ),
        metadata={
            "strategy_family": StrategyType.COMPRESSION_EXPANSION.value,
            "source_strategy": StrategyType.BREAKOUT_CONTINUATION.value,
            "compression_expansion_regime": regime,
        },
        entry_opportunities=(entry,),
        provisional=provisional,
    )


@pytest.mark.parametrize("regime", ("compression", "breakout_expansion"))
def test_supported_regimes_map_to_common_contract(regime: str) -> None:
    profile = compression_expansion_archetype_profile(_candidate(regime=regime))

    assert profile.archetype is ArchetypeFamily.COMPRESSION_EXPANSION
    assert profile.strategy is StrategyType.COMPRESSION_EXPANSION
    assert profile.entry_modes == (EntryMode.MOMENTUM_CONTINUATION,)
    assert profile.invalidation_type is InvalidationType.STRUCTURAL
    assert profile.target_types == (TargetType.EXPANSION,)
    assert profile.regime_eligible is True
    assert profile.confirmation_complete is True
    assert regime in profile.explanation_labels


def test_profile_preserves_lineage_and_existing_optional_evidence() -> None:
    profile = compression_expansion_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit compression-expansion family metadata",
        "momentum evidence",
        "liquidity evidence",
    )


@pytest.mark.parametrize(
    "candidate",
    (
        _candidate(regime="range"),
        _candidate(include_regime_evidence=False),
        _candidate(include_release_evidence=False),
        _candidate(include_structure_reference=False),
    ),
)
def test_eligibility_requires_existing_generator_facts(candidate: TradeCandidate) -> None:
    profile = compression_expansion_archetype_profile(candidate)

    assert profile.regime_eligible is False
    assert profile.confirmation_complete is False


def test_provisional_state_is_visible_without_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)

    profile = compression_expansion_archetype_profile(candidate)

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
        strategy=StrategyType.BREAKOUT_CONTINUATION,
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
        match="compression-expansion profile requires a compression-expansion candidate",
    ):
        compression_expansion_archetype_profile(wrong)
