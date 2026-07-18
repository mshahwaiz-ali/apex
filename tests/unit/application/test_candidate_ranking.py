"""Tests for typed primary and alternative candidate ranking snapshots."""

from datetime import UTC, datetime

from apex.application.candidate_ranking import (
    CandidateRankingRole,
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.scoring import analyze_candidate_selection
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyAnalysisResult,
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
    quality: float,
    entry_low: float = 99.0,
    entry_high: float = 101.0,
    entry_preferred: float = 100.0,
    invalidation_price: float = 95.0,
    target_price: float = 110.0,
) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_low,
            upper=entry_high,
            preferred=entry_preferred,
            current_price=entry_preferred,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=quality,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation_price,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target_price,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=quality,
            structure_quality=quality,
            entry_quality=quality,
            momentum_quality=quality,
            volume_quality=quality,
            liquidity_quality=quality,
            target_space_quality=quality,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={"entry_confirmation_complete": True},
    )


def test_snapshot_preserves_primary_and_viable_alternative() -> None:
    strategy_analysis = StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(
            _candidate(StrategyType.TREND_PULLBACK, quality=0.95),
            _candidate(
                StrategyType.BREAKOUT_CONTINUATION,
                quality=0.90,
                entry_low=102.0,
                entry_high=104.0,
                entry_preferred=103.0,
                invalidation_price=98.0,
                target_price=114.0,
            ),
        ),
        evaluated_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.BREAKOUT_CONTINUATION,
        ),
    )
    candidate_selection = analyze_candidate_selection(strategy_analysis)
    snapshot = build_candidate_ranking_snapshot(candidate_selection)

    assert snapshot.primary is not None
    assert snapshot.primary.role is CandidateRankingRole.PRIMARY
    assert snapshot.primary.rank == 1
    assert snapshot.alternatives
    assert snapshot.alternatives[0].role is CandidateRankingRole.ALTERNATIVE
    assert snapshot.alternatives[0].rank == 2
    assert snapshot.ranked_count == 2


def test_payload_keeps_deterministic_rank_order() -> None:
    strategy_analysis = StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(
            _candidate(StrategyType.TREND_PULLBACK, quality=0.95),
            _candidate(
                StrategyType.BREAKOUT_CONTINUATION,
                quality=0.90,
                entry_low=102.0,
                entry_high=104.0,
                entry_preferred=103.0,
                invalidation_price=98.0,
                target_price=114.0,
            ),
        ),
        evaluated_strategies=(
            StrategyType.TREND_PULLBACK,
            StrategyType.BREAKOUT_CONTINUATION,
        ),
    )
    payload = candidate_ranking_payload(
        build_candidate_ranking_snapshot(analyze_candidate_selection(strategy_analysis))
    )

    assert payload["primary"]["rank"] == 1  # type: ignore[index]
    assert payload["alternatives"][0]["rank"] == 2  # type: ignore[index]
    assert payload["ranked_count"] == 2
    assert payload["alternative_count"] == 1
