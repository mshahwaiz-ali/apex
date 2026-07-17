"""Tests for soft strategy-applicability weighting."""

from datetime import UTC, datetime

import pytest

from apex.scoring.applicability import apply_strategy_applicability
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.scoring.scorer import score_candidates
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyApplicability,
    StrategyApplicabilityState,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)


NOW = datetime(2026, 7, 17, tzinfo=UTC)


def _candidate(strategy: StrategyType) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
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
            location_quality=0.9,
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
            trend_alignment=0.8,
            structure_quality=0.8,
            entry_quality=0.8,
            momentum_quality=0.8,
            volume_quality=0.8,
            liquidity_quality=0.8,
            target_space_quality=0.8,
        ),
        evidence=StrategyEvidence(
            supporting=("test evidence",),
        ),
        metadata={},
    )


def _record(
    strategy: StrategyType,
    state: StrategyApplicabilityState,
    score: float,
) -> StrategyApplicability:
    return StrategyApplicability(
        strategy=strategy,
        state=state,
        score=score,
        reason_codes=("TEST",),
        reasons=("test applicability",),
    )


def test_applicable_candidate_score_is_unchanged() -> None:
    candidate = _candidate(StrategyType.TREND_PULLBACK)
    scored = score_candidates(
        (candidate,),
        config=DEFAULT_SCORING_CONFIG,
    )

    adjusted = apply_strategy_applicability(
        scored,
        applicability={
            candidate.strategy: _record(
                candidate.strategy,
                StrategyApplicabilityState.APPLICABLE,
                100.0,
            )
        },
    )

    assert adjusted == scored


def test_conditional_candidate_receives_transparent_penalty() -> None:
    candidate = _candidate(StrategyType.BREAKOUT_CONTINUATION)
    scored = score_candidates(
        (candidate,),
        config=DEFAULT_SCORING_CONFIG,
    )

    adjusted = apply_strategy_applicability(
        scored,
        applicability={
            candidate.strategy: _record(
                candidate.strategy,
                StrategyApplicabilityState.CONDITIONAL,
                65.0,
            )
        },
    )

    assert adjusted[0].final_score == pytest.approx(
        scored[0].final_score - 7.0
    )
    assert adjusted[0].breakdown.penalty_points[
        "strategy_applicability"
    ] == pytest.approx(7.0)
    assert (
        "conditional strategy applicability penalty applied"
        in adjusted[0].notes
    )


def test_not_applicable_candidate_is_rejected_before_ranking() -> None:
    candidate = _candidate(StrategyType.RANGE_REVERSAL)
    scored = score_candidates(
        (candidate,),
        config=DEFAULT_SCORING_CONFIG,
    )

    with pytest.raises(
        ValueError,
        match="not-applicable strategy candidate reached candidate scoring",
    ):
        apply_strategy_applicability(
            scored,
            applicability={
                candidate.strategy: _record(
                    candidate.strategy,
                    StrategyApplicabilityState.NOT_APPLICABLE,
                    0.0,
                )
            },
        )
