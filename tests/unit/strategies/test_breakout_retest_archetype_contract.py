from __future__ import annotations

from datetime import UTC, datetime

import pytest

from apex.strategies.archetype_contract import (
    ArchetypeFamily,
    breakout_retest_archetype_profile,
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
    provisional: bool = False,
    breakout_context: bool = True,
    include_family_metadata: bool = True,
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
        mode=EntryMode.RETEST,
        rationale=("confirmed breakout retest",),
        max_chase_price=102.0,
    )
    supporting = (
        (
            "confirmed breakout context is being retested",
            "higher-timeframe breakout expansion establishes continuation context",
            "lower-timeframe structure provides the retest or reclaim execution geometry",
        )
        if breakout_context
        else ("lower-timeframe pullback geometry exists",)
    )
    metadata: dict[str, str | bool] = {
        "source_strategy": StrategyType.TREND_PULLBACK.value,
        "higher_timeframe_breakout_continuation": breakout_context,
    }
    if include_family_metadata:
        metadata["strategy_family"] = StrategyType.BREAKOUT_RETEST.value

    return TradeCandidate(
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_RETEST,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=entry,
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=97.0,
            rationale=("retest structure failed",),
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
            structure_quality=0.9,
            entry_quality=0.9,
            momentum_quality=0.7,
            volume_quality=0.6,
            liquidity_quality=0.6,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=supporting,
            warnings=(("active-candle evidence is provisional",) if provisional else ()),
            feature_references=("ema_fast", "vwap"),
            structure_references=(
                "trend",
                "breaks",
                "levels",
                "higher_timeframe_breakout",
                "breakout_retest",
            ),
            liquidity_references=("opposing_liquidity",),
        ),
        metadata=metadata,
        entry_opportunities=(entry,),
        provisional=provisional,
    )


def test_breakout_retest_maps_to_common_archetype_contract() -> None:
    profile = breakout_retest_archetype_profile(_candidate())

    assert profile.archetype is ArchetypeFamily.BREAKOUT_RETEST
    assert profile.strategy is StrategyType.BREAKOUT_RETEST
    assert profile.entry_modes == (EntryMode.RETEST,)
    assert profile.invalidation_type is InvalidationType.STRUCTURAL
    assert profile.target_types == (TargetType.STRUCTURAL,)
    assert profile.confirmation_complete is True
    assert profile.regime_eligible is True
    assert profile.provisional is False


def test_breakout_retest_preserves_lineage_and_optional_evidence() -> None:
    profile = breakout_retest_archetype_profile(_candidate())

    assert profile.optional_evidence == (
        "source strategy lineage",
        "explicit breakout-retest family metadata",
        "higher-timeframe breakout continuation",
        "liquidity evidence",
    )
    assert profile.explanation_labels == (
        "breakout retest",
        "confirmation complete",
        "closed evidence",
    )


def test_provisional_retest_is_visible_without_candidate_mutation() -> None:
    candidate = _candidate(provisional=True)
    original_metadata = dict(candidate.metadata)
    original_entry = candidate.entry

    profile = breakout_retest_archetype_profile(candidate)

    assert profile.confirmation_complete is False
    assert profile.provisional is True
    assert profile.contradictions == ("active-candle evidence is provisional",)
    assert candidate.entry is original_entry
    assert dict(candidate.metadata) == original_metadata


def test_missing_breakout_context_marks_profile_ineligible() -> None:
    profile = breakout_retest_archetype_profile(
        _candidate(breakout_context=False, include_family_metadata=False)
    )

    assert profile.regime_eligible is False
    assert profile.confirmation_complete is False
    assert profile.optional_evidence == (
        "source strategy lineage",
        "liquidity evidence",
    )


def test_non_breakout_retest_candidate_is_rejected() -> None:
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
        match="breakout-retest profile requires a breakout-retest candidate",
    ):
        breakout_retest_archetype_profile(wrong)
