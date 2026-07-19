from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    momentum_continuation_archetype_profile,
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
    confirmation_complete: bool,
    provisional: bool = False,
    higher_timeframe_conflict: bool = False,
) -> TradeCandidate:
    primary = EntryZone(
        lower=99.0,
        upper=101.0,
        preferred=100.0,
        current_price=100.0,
        distance_from_current=0.0,
        atr_distance=0.0,
        estimated_move_missed=0.0,
        location_quality=0.9,
        mode=EntryMode.MOMENTUM_CONTINUATION,
        rationale=("near-CMP continuation entry",),
        max_chase_price=102.0,
    )
    retest = EntryZone(
        lower=98.5,
        upper=99.5,
        preferred=99.0,
        current_price=100.0,
        distance_from_current=1.0,
        atr_distance=0.5,
        estimated_move_missed=0.0,
        location_quality=0.95,
        mode=EntryMode.RETEST,
        rationale=("retest alternative",),
        max_chase_price=100.5,
    )
    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=primary,
        invalidation=InvalidationConcept(
            kind=InvalidationType.VOLATILITY,
            price=97.0,
            rationale=("momentum thesis failure",),
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
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.9,
            momentum_quality=0.8,
            volume_quality=0.7,
            liquidity_quality=0.5,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=(
                "directional trend or recent structural continuation is present",
                "2 of 3 available momentum measures align",
            ),
            warnings=(
                ("higher-timeframe trend conflicts with the decision-frame momentum thesis",)
                if higher_timeframe_conflict
                else ()
            ),
            feature_references=(
                "rate_of_change",
                "macd_histogram",
                "relative_volume",
                "ema_fast",
                "vwap",
            ),
            structure_references=("trend", "breaks", "levels"),
        ),
        metadata={
            "entry_confirmation_complete": confirmation_complete,
            "recent_continuation_break": True,
            "higher_timeframe_conflict": higher_timeframe_conflict,
        },
        entry_opportunities=(primary, retest),
        provisional=provisional,
    )


def test_momentum_candidate_maps_to_common_archetype_contract() -> None:
    profile = momentum_continuation_archetype_profile(_candidate(confirmation_complete=True))

    assert profile.archetype is ArchetypeFamily.MOMENTUM_CONTINUATION
    assert profile.strategy is StrategyType.MOMENTUM_BREAKOUT
    assert profile.confirmation_complete is True
    assert profile.provisional is False
    assert profile.regime_eligible is True
    assert profile.entry_modes == (
        EntryMode.MOMENTUM_CONTINUATION,
        EntryMode.RETEST,
    )
    assert profile.invalidation_type is InvalidationType.VOLATILITY
    assert profile.target_types == (TargetType.EXPANSION,)


def test_profile_preserves_optional_evidence_and_conflicts() -> None:
    profile = momentum_continuation_archetype_profile(
        _candidate(
            confirmation_complete=False,
            provisional=True,
            higher_timeframe_conflict=True,
        )
    )

    assert profile.confirmation_complete is False
    assert profile.provisional is True
    assert "relative volume" in profile.optional_evidence
    assert "fast EMA continuation reference" in profile.optional_evidence
    assert "VWAP continuation reference" in profile.optional_evidence
    assert "higher-timeframe alignment" not in profile.optional_evidence
    assert profile.contradictions == (
        "higher-timeframe trend conflicts with the decision-frame momentum thesis",
    )
    assert profile.explanation_labels == (
        "momentum continuation",
        "confirmation incomplete",
        "provisional evidence",
    )


def test_profile_does_not_mutate_candidate_behavior() -> None:
    candidate = _candidate(confirmation_complete=False)
    original_entry = candidate.entry
    original_metadata = dict(candidate.metadata)
    original_evidence = candidate.evidence

    profile = momentum_continuation_archetype_profile(candidate)

    assert profile.confirmation_complete is False
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata
    assert candidate.evidence is original_evidence


def test_non_momentum_candidate_is_rejected_by_specific_adapter() -> None:
    candidate = _candidate(confirmation_complete=True)
    wrong = TradeCandidate(
        symbol=candidate.symbol,
        strategy=StrategyType.BREAKOUT_RETEST,
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
        match="momentum continuation profile requires a momentum-breakout candidate",
    ):
        momentum_continuation_archetype_profile(wrong)
