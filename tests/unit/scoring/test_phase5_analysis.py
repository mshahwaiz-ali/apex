from datetime import UTC, datetime
from types import MappingProxyType

import pytest

from apex.scoring import (
    CandidateOutcome,
    DirectionalConsensus,
    PenaltyWeights,
    ScoringConfig,
    ScoringWeights,
    analyze_phase5,
)
from apex.scoring.ranking import rank_candidates
from apex.scoring.scorer import score_candidates
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

NOW = datetime(2026, 7, 13, tzinfo=UTC)
ORDER = tuple(StrategyType)


def _candidate(
    *,
    strategy: StrategyType = StrategyType.TREND_PULLBACK,
    direction: TradeDirection = TradeDirection.LONG,
    quality: float = 0.8,
    entry_lower: float = 99.0,
    entry_upper: float = 101.0,
    invalidation: float | None = None,
    target: float | None = None,
    provisional: bool = False,
    extension_penalty: float = 0.0,
    conflict_penalty: float = 0.0,
    metadata: dict[str, str | int | float | bool] | None = None,
) -> TradeCandidate:
    if invalidation is None:
        invalidation = 98.0 if direction is TradeDirection.LONG else 102.0
    if target is None:
        target = 104.0 if direction is TradeDirection.LONG else 96.0
    preferred = (entry_lower + entry_upper) / 2.0
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
        direction=direction,
        decision_time=NOW,
        entry=EntryZone(
            lower=entry_lower,
            upper=entry_upper,
            preferred=preferred,
            current_price=100.0,
            distance_from_current=abs(preferred - 100.0),
            atr_distance=abs(preferred - 100.0),
            estimated_move_missed=0.0,
            location_quality=quality,
            mode=EntryMode.MARKET_NEAR,
            rationale=("actionable entry",),
        ),
        invalidation=InvalidationConcept(
            kind=InvalidationType.STRUCTURAL,
            price=invalidation,
            rationale=("thesis invalidated",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=target,
                    label="primary",
                    rationale=("target space",),
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
            extension_penalty=extension_penalty,
            conflict_penalty=conflict_penalty,
        ),
        evidence=StrategyEvidence(
            supporting=("valid deterministic thesis",),
            structure_references=("level:100",),
        ),
        metadata={} if metadata is None else metadata,
        provisional=provisional,
    )


def _phase4(*candidates: TradeCandidate) -> Phase4AnalysisResult:
    ordered = tuple(sorted(candidates, key=lambda item: ORDER.index(item.strategy)))
    return Phase4AnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=ordered,
        evaluated_strategies=ORDER,
    )


def test_perfect_candidate_scores_100() -> None:
    scored = score_candidates((_candidate(quality=1.0),), config=ScoringConfig())
    assert scored[0].final_score == pytest.approx(100.0)


def test_penalties_are_explicit_and_bounded() -> None:
    candidate = _candidate(
        quality=1.0,
        extension_penalty=1.0,
        conflict_penalty=1.0,
        provisional=True,
    )
    scored = score_candidates((candidate,), config=ScoringConfig())[0]
    assert scored.final_score == pytest.approx(65.0)
    assert scored.breakdown.total_penalty == pytest.approx(35.0)
    assert isinstance(scored.breakdown.quality_points, MappingProxyType)


def test_higher_timeframe_contradiction_is_penalized() -> None:
    candidate = _candidate(
        quality=1.0,
        metadata={"higher_timeframe_contradiction": 1.0},
    )
    scored = score_candidates((candidate,), config=ScoringConfig())[0]
    assert scored.final_score == pytest.approx(82.0)


def test_invalid_weights_are_rejected() -> None:
    with pytest.raises(ValueError, match="sum to one"):
        ScoringWeights(trend_alignment=0.15)
    with pytest.raises(ValueError, match="non-negative"):
        PenaltyWeights(extension_penalty=-1.0)


def test_scoring_does_not_mutate_raw_candidate() -> None:
    candidate = _candidate()
    before = candidate
    first = score_candidates((candidate,), config=ScoringConfig())
    second = score_candidates((candidate,), config=ScoringConfig())
    assert candidate == before
    assert first == second


def test_scoring_config_fingerprint_is_stable_and_sensitive() -> None:
    base = ScoringConfig()
    same = ScoringConfig()
    changed = ScoringConfig(minimum_accept_score=60.0)

    assert base.fingerprint() == same.fingerprint()
    assert base.fingerprint() != changed.fingerprint()


def test_ranking_is_input_order_independent() -> None:
    stronger = _candidate(strategy=StrategyType.BREAKOUT_CONTINUATION, quality=0.9)
    weaker = _candidate(strategy=StrategyType.TREND_PULLBACK, quality=0.7)
    config = ScoringConfig()
    forward = rank_candidates(
        score_candidates((stronger, weaker), config=config), strategy_order=ORDER
    )
    reverse = rank_candidates(
        score_candidates((weaker, stronger), config=config), strategy_order=ORDER
    )
    assert tuple(item.candidate.strategy for item in forward) == tuple(
        item.candidate.strategy for item in reverse
    )


def test_registry_order_and_direction_break_ties() -> None:
    long = _candidate(strategy=StrategyType.TREND_PULLBACK)
    short = _candidate(strategy=StrategyType.TREND_PULLBACK, direction=TradeDirection.SHORT)
    breakout = _candidate(strategy=StrategyType.BREAKOUT_CONTINUATION)
    config = ScoringConfig()
    ranked = rank_candidates(
        score_candidates((breakout, short, long), config=config), strategy_order=ORDER
    )
    assert [item.candidate.direction for item in ranked[:2]] == [
        TradeDirection.LONG,
        TradeDirection.SHORT,
    ]
    assert ranked[2].candidate.strategy is StrategyType.BREAKOUT_CONTINUATION


def test_clear_long_winner_is_selected() -> None:
    result = analyze_phase5(
        _phase4(
            _candidate(quality=0.9),
            _candidate(
                strategy=StrategyType.BREAKOUT_CONTINUATION,
                direction=TradeDirection.SHORT,
                quality=0.55,
            ),
        )
    )
    assert result.selected_direction is TradeDirection.LONG
    assert result.directional_consensus is DirectionalConsensus.MIXED


def test_clear_short_winner_is_selected() -> None:
    result = analyze_phase5(_phase4(_candidate(direction=TradeDirection.SHORT, quality=0.9)))
    assert result.selected_direction is TradeDirection.SHORT


def test_equal_opposing_strength_returns_no_trade() -> None:
    result = analyze_phase5(
        _phase4(
            _candidate(quality=0.85),
            _candidate(
                strategy=StrategyType.BREAKOUT_CONTINUATION,
                direction=TradeDirection.SHORT,
                quality=0.85,
            ),
        )
    )
    assert result.selected_candidate is None
    assert result.no_trade_reason is not None
    assert "unresolved" in result.no_trade_reason


def test_provisional_aggressive_candidate_is_accepted_with_warning() -> None:
    result = analyze_phase5(_phase4(_candidate(quality=0.75, provisional=True)))
    assert result.selected_candidate is not None
    assert result.selected_candidate.outcome is CandidateOutcome.ACCEPTED_WITH_WARNING


def test_duplicate_thesis_is_grouped_not_double_selected() -> None:
    result = analyze_phase5(
        _phase4(
            _candidate(strategy=StrategyType.TREND_PULLBACK, quality=0.85),
            _candidate(strategy=StrategyType.MOMENTUM_CONTINUATION, quality=0.82),
        )
    )
    assert len(result.conflict_summary.duplicate_groups) == 1
    assert result.metadata["duplicate_cluster_count"] == 1
    assert isinstance(result.metadata["config_hash"], str)
    assert len(result.metadata["config_hash"]) == 64
    assert len(result.rejected_candidates) == 1
    assert result.rejected_candidates[0].outcome is CandidateOutcome.REJECTED_DUPLICATE


def test_all_candidates_below_threshold_returns_no_trade() -> None:
    result = analyze_phase5(_phase4(_candidate(quality=0.3)))
    assert result.selected_candidate is None
    assert result.rejected_candidates[0].outcome is CandidateOutcome.REJECTED_BELOW_THRESHOLD


def test_major_higher_timeframe_contradiction_is_rejected() -> None:
    result = analyze_phase5(
        _phase4(
            _candidate(
                quality=0.95,
                metadata={"higher_timeframe_contradiction": 1.0},
            )
        )
    )
    assert result.selected_candidate is None
    assert result.rejected_candidates[0].outcome is CandidateOutcome.REJECTED_CONTRADICTION


def test_empty_phase4_result_is_explicit_no_trade() -> None:
    result = analyze_phase5(_phase4())
    assert result.selected_candidate is None
    assert result.no_trade_reason == "no Phase 4 candidates were generated"
