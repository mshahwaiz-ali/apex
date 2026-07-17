"""Tests for penalty-aware redesigned ranking scores."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
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


def _candidate(*, provisional: bool, contradiction: float) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=StrategyType.TREND_PULLBACK,
        direction=TradeDirection.LONG,
        decision_time=NOW,
        entry=EntryZone(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            distance_from_current=0.0,
            atr_distance=0.0,
            estimated_move_missed=0.0,
            location_quality=0.80,
            mode=EntryMode.MARKET_NEAR,
            rationale=("test entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=95.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=110.0,
                    label="TP1",
                    rationale=("test target",),
                ),
            )
        ),
        quality=RawQualityMetrics(
            trend_alignment=0.80,
            structure_quality=0.80,
            entry_quality=0.80,
            momentum_quality=0.80,
            volume_quality=0.80,
            liquidity_quality=0.80,
            target_space_quality=0.80,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        provisional=provisional,
        metadata={"higher_timeframe_contradiction": contradiction},
    )


def _snapshot(*, provisional: bool, contradiction: float):
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(
            _candidate(
                provisional=provisional,
                contradiction=contradiction,
            ),
        ),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
    )
    return build_candidate_ranking_snapshot(analyze_candidate_selection(phase4))


def test_rank_score_subtracts_existing_measured_penalties() -> None:
    snapshot = _snapshot(provisional=True, contradiction=0.50)

    assert snapshot.primary is not None
    assert snapshot.primary.unpenalized_rank_score == 80.0
    assert snapshot.primary.rank_penalty_score == 17.0
    assert snapshot.primary.final_rank_score == 63.0


def test_unpenalized_candidate_keeps_full_rank_score() -> None:
    snapshot = _snapshot(provisional=False, contradiction=0.0)

    assert snapshot.primary is not None
    assert snapshot.primary.unpenalized_rank_score == 80.0
    assert snapshot.primary.rank_penalty_score == 0.0
    assert snapshot.primary.final_rank_score == 80.0


def test_payload_exposes_rank_penalty_diagnostics() -> None:
    payload = candidate_ranking_payload(
        _snapshot(provisional=True, contradiction=0.50)
    )
    primary = payload["primary"]

    assert primary["unpenalized_rank_score"] == 80.0  # type: ignore[index]
    assert primary["rank_penalty_score"] == 17.0  # type: ignore[index]
    assert primary["final_rank_score"] == 63.0  # type: ignore[index]
