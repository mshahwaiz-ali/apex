"""Tests for redesigned candidate ranking order."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.scoring import analyze_candidate_selection
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    Phase4AnalysisResult,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)


NOW = datetime(2026, 7, 17, tzinfo=UTC)


def _candidate(
    strategy: StrategyType,
    *,
    quality: RawQualityMetrics,
    entry_preferred: float,
) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_preferred - 1.0,
            upper=entry_preferred + 1.0,
            preferred=entry_preferred,
            current_price=entry_preferred,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=quality.entry_quality,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=entry_preferred - 5.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=entry_preferred + 10.0,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        quality=quality,
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={},
    )


def test_phase5_ranks_by_redesigned_final_rank_score() -> None:
    legacy_favorite = _candidate(
        StrategyType.TREND_PULLBACK,
        quality=RawQualityMetrics(
            trend_alignment=0.0,
            structure_quality=0.7,
            entry_quality=0.0,
            momentum_quality=1.0,
            volume_quality=0.0,
            liquidity_quality=1.0,
            target_space_quality=1.0,
        ),
        entry_preferred=100.0,
    )
    redesign_favorite = _candidate(
        StrategyType.BREAKOUT_CONTINUATION,
        quality=RawQualityMetrics(
            trend_alignment=1.0,
            structure_quality=0.2,
            entry_quality=1.0,
            momentum_quality=0.0,
            volume_quality=1.0,
            liquidity_quality=0.0,
            target_space_quality=0.0,
        ),
        entry_preferred=120.0,
    )
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(legacy_favorite, redesign_favorite),
        evaluated_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.BREAKOUT_CONTINUATION,
        ),
    )

    result = analyze_candidate_selection(phase4)

    assert result.all_scored_candidates[0].final_score == 51.9
    assert result.all_scored_candidates[1].final_score == 46.4
    assert result.ranked_candidates[0].candidate.strategy is StrategyType.BREAKOUT_CONTINUATION
    assert result.ranked_candidates[0].tie_break[0] == "final_rank_score=51.000000"
    assert result.ranked_candidates[1].tie_break[0] == "final_rank_score=47.250000"


def test_redesigned_ranking_does_not_change_legacy_threshold_outcomes() -> None:
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(
            _candidate(
                StrategyType.TREND_PULLBACK,
                quality=RawQualityMetrics(
                    trend_alignment=0.0,
                    structure_quality=0.7,
                    entry_quality=0.0,
                    momentum_quality=1.0,
                    volume_quality=0.0,
                    liquidity_quality=1.0,
                    target_space_quality=1.0,
                ),
                entry_preferred=100.0,
            ),
        ),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
    )

    result = analyze_candidate_selection(phase4)

    assert result.ranked_candidates[0].final_score == 51.9
    assert result.ranked_candidates[0].outcome.value == "rejected_below_score_threshold"
    assert result.selected_candidate is None
