from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from apex.scoring import (
    CandidateOutcome,
    ConflictSummary,
    DirectionalConsensus,
    Phase5AnalysisResult,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.strategies import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ORDER = tuple(StrategyType)


def _candidate() -> TradeCandidate:
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
            location_quality=0.8,
            mode=EntryMode.MARKET_NEAR,
            rationale=("actionable entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=98.0,
            rationale=("structure fails",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=104.0,
                    label="primary",
                    rationale=("target space",),
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
        evidence=StrategyEvidence(supporting=("valid thesis",)),
        metadata={},
    )


def _scored(candidate_id: str = "trend_pullback:long:0") -> ScoredCandidate:
    return ScoredCandidate(
        candidate_id=candidate_id,
        candidate=_candidate(),
        breakdown=ScoreBreakdown(
            quality_points={"entry_quality": 80.0},
            penalty_points={"conflict_penalty": 0.0},
            base_score=80.0,
            total_penalty=0.0,
            final_score=80.0,
        ),
        normalized_metrics={"entry_quality": 0.8},
    )


def _ranked(
    *,
    candidate_id: str = "trend_pullback:long:0",
    rank: int = 1,
    outcome: CandidateOutcome = CandidateOutcome.ACCEPTED,
    reasons: tuple[str, ...] = (),
) -> RankedCandidate:
    return RankedCandidate(
        scored=_scored(candidate_id),
        rank=rank,
        outcome=outcome,
        reasons=reasons,
        tie_break=("deterministic",),
    )


def _summary() -> ConflictSummary:
    return ConflictSummary(
        directional_consensus=DirectionalConsensus.LONG,
        long_count=1,
        short_count=0,
        duplicate_groups=(),
        warnings=(),
    )


@pytest.mark.parametrize("value", [-1.0, 101.0, float("nan"), float("inf")])
def test_score_breakdown_rejects_non_finite_or_unbounded_scores(value: float) -> None:
    with pytest.raises(ValueError, match="between zero and 100"):
        ScoreBreakdown(
            quality_points={"entry_quality": 1.0},
            penalty_points={},
            base_score=value,
            total_penalty=0.0,
            final_score=50.0,
        )


def test_score_and_metric_mappings_are_immutable_copies() -> None:
    quality = {"entry_quality": 80.0}
    metrics = {"entry_quality": 0.8}
    scored = ScoredCandidate(
        candidate_id="trend_pullback:long:0",
        candidate=_candidate(),
        breakdown=ScoreBreakdown(
            quality_points=quality,
            penalty_points={},
            base_score=80.0,
            total_penalty=0.0,
            final_score=80.0,
        ),
        normalized_metrics=metrics,
    )
    quality["entry_quality"] = 1.0
    metrics["entry_quality"] = 0.1

    assert isinstance(scored.breakdown.quality_points, MappingProxyType)
    assert isinstance(scored.normalized_metrics, MappingProxyType)
    assert scored.breakdown.quality_points["entry_quality"] == 80.0
    assert scored.normalized_metrics["entry_quality"] == 0.8


def test_rank_must_be_positive() -> None:
    with pytest.raises(ValueError, match="rank must be positive"):
        _ranked(rank=0)


def test_rejected_candidate_requires_reason() -> None:
    with pytest.raises(ValueError, match="rejection reasons cannot be empty"):
        _ranked(outcome=CandidateOutcome.REJECTED_BELOW_THRESHOLD)


def test_result_requires_aware_decision_time() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        Phase5AnalysisResult(
            symbol="BTC/USDT",
            decision_time=datetime(2026, 7, 13),
            all_scored_candidates=(),
            ranked_candidates=(),
            rejected_candidates=(),
            conflict_summary=ConflictSummary(
                directional_consensus=DirectionalConsensus.NONE,
                long_count=0,
                short_count=0,
                duplicate_groups=(),
                warnings=(),
            ),
            directional_consensus=DirectionalConsensus.NONE,
            selected_candidate=None,
            no_trade_reason="no candidates",
            evaluated_strategy_order=ORDER,
            configuration_id="test",
            metadata={},
        )


def test_result_rejects_duplicate_candidate_identities() -> None:
    first = _scored()
    second = _scored()
    with pytest.raises(ValueError, match="identities must be unique"):
        Phase5AnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            all_scored_candidates=(first, second),
            ranked_candidates=(),
            rejected_candidates=(),
            conflict_summary=_summary(),
            directional_consensus=DirectionalConsensus.LONG,
            selected_candidate=None,
            no_trade_reason="duplicates invalidated result",
            evaluated_strategy_order=ORDER,
            configuration_id="test",
            metadata={},
        )


def test_selected_candidate_must_belong_to_ranked_candidates() -> None:
    selected = _ranked(candidate_id="trend_pullback:long:0")
    other = _ranked(candidate_id="trend_pullback:long:1")
    with pytest.raises(ValueError, match="selected candidate must belong"):
        Phase5AnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            all_scored_candidates=(selected.scored, other.scored),
            ranked_candidates=(other,),
            rejected_candidates=(),
            conflict_summary=_summary(),
            directional_consensus=DirectionalConsensus.LONG,
            selected_candidate=selected,
            no_trade_reason=None,
            evaluated_strategy_order=ORDER,
            configuration_id="test",
            metadata={},
        )


def test_selected_trade_cannot_also_have_no_trade_reason() -> None:
    selected = _ranked()
    with pytest.raises(ValueError, match="cannot also have"):
        Phase5AnalysisResult(
            symbol="BTC/USDT",
            decision_time=NOW,
            all_scored_candidates=(selected.scored,),
            ranked_candidates=(selected,),
            rejected_candidates=(),
            conflict_summary=_summary(),
            directional_consensus=DirectionalConsensus.LONG,
            selected_candidate=selected,
            no_trade_reason="contradictory state",
            evaluated_strategy_order=ORDER,
            configuration_id="test",
            metadata={},
        )
