"""Tests for weighted candidate ranking score output."""

from __future__ import annotations

from datetime import UTC, datetime

from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.scoring import analyze_phase5
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


def _snapshot():
    candidate = TradeCandidate(
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
            trend_alignment=0.90,
            structure_quality=0.70,
            entry_quality=0.60,
            momentum_quality=0.80,
            volume_quality=0.40,
            liquidity_quality=0.60,
            target_space_quality=0.75,
        ),
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={},
    )
    phase4 = Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.TREND_PULLBACK,),
    )
    return build_candidate_ranking_snapshot(analyze_phase5(phase4))


def test_dimensions_use_redesign_contract_names() -> None:
    snapshot = _snapshot()

    assert snapshot.primary is not None
    dimensions = snapshot.primary.score_dimensions
    assert dimensions.opportunity_score == 60.0
    assert dimensions.setup_score == 80.0
    assert dimensions.timing_score == 60.0
    assert dimensions.risk_feasibility_score == 75.0


def test_weighted_final_rank_score_is_deterministic() -> None:
    snapshot = _snapshot()

    assert snapshot.primary is not None
    assert snapshot.primary.final_rank_score == 69.25
    assert snapshot.primary.final_score == 69.65
    assert snapshot.primary.rank == 1


def test_payload_exposes_final_rank_score_and_weights() -> None:
    payload = candidate_ranking_payload(_snapshot())
    primary = payload["primary"]

    assert primary["final_rank_score"] == 69.25  # type: ignore[index]
    assert primary["score_dimensions"]["risk_feasibility_score"] == 75.0  # type: ignore[index]
    assert payload["rank_score_weights"] == {
        "opportunity_score": 0.30,
        "setup_score": 0.35,
        "timing_score": 0.20,
        "risk_feasibility_score": 0.15,
    }
