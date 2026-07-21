"""Tests for soft market-environment route alignment."""

from datetime import UTC, datetime

import pytest

from apex.application.market_strategy_router import MarketStrategyRoute, PreferredDirection
from apex.scoring import analyze_candidate_selection
from apex.scoring.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from apex.scoring.contracts import EnvironmentRouteAlignmentState
from apex.scoring.environment_route import apply_environment_route_alignment
from apex.scoring.rank_score import final_rank_score, rank_penalty_score
from apex.scoring.scorer import score_candidates
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
    direction: TradeDirection = TradeDirection.LONG,
) -> TradeCandidate:
    return TradeCandidate(
        symbol="BTC/USDT",
        strategy=strategy,
        direction=direction,
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
            price=95.0 if direction is TradeDirection.LONG else 105.0,
            rationale=("test invalidation",),
        ),
        targets=TargetConcept(
            levels=(
                TargetLevel(
                    kind=TargetType.STRUCTURAL,
                    price=110.0 if direction is TradeDirection.LONG else 90.0,
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
        evidence=StrategyEvidence(supporting=("test evidence",)),
        metadata={},
    )


def _route(**overrides: object) -> MarketStrategyRoute:
    values: dict[str, object] = {
        "allowed_strategies": (
            StrategyType.BREAKOUT_CONTINUATION,
            StrategyType.TREND_PULLBACK,
        ),
        "blocked_strategies": (),
        "preferred_direction": PreferredDirection.LONG,
        "strategy_priority": (
            StrategyType.BREAKOUT_CONTINUATION,
            StrategyType.TREND_PULLBACK,
        ),
        "routing_score": 80.0,
        "reason_codes": ("REGIME_ROUTE_APPLIED",),
        "reasons": ("test route",),
    }
    values.update(overrides)
    return MarketStrategyRoute(**values)  # type: ignore[arg-type]


def test_canonical_route_candidate_keeps_score() -> None:
    scored = score_candidates(
        (_candidate(StrategyType.BREAKOUT_CONTINUATION),),
        config=DEFAULT_SCORING_CONFIG,
    )

    adjusted = apply_environment_route_alignment(scored, route=_route())

    assert adjusted[0].final_score == scored[0].final_score
    assert adjusted[0].environment_route_alignment is not None
    assert adjusted[0].environment_route_alignment.state is EnvironmentRouteAlignmentState.ALIGNED
    assert adjusted[0].environment_route_alignment.route_priority == 1
    assert adjusted[0].environment_route_alignment.score_adjustment == 0.0


def test_lower_priority_alternative_remains_rankable_with_modest_penalty() -> None:
    scored = score_candidates(
        (_candidate(StrategyType.RANGE_REVERSAL),),
        config=DEFAULT_SCORING_CONFIG,
    )

    adjusted = apply_environment_route_alignment(scored, route=_route())

    assert adjusted[0].final_score == scored[0].final_score
    assert rank_penalty_score(adjusted[0]) == pytest.approx(6.0)
    assert final_rank_score(adjusted[0]) < final_rank_score(scored[0])
    assert adjusted[0].environment_route_alignment is not None
    assert (
        adjusted[0].environment_route_alignment.state
        is EnvironmentRouteAlignmentState.LOWER_PRIORITY
    )
    assert "STRATEGY_OUTSIDE_ROUTE_PRIORITY" in (
        adjusted[0].environment_route_alignment.reason_codes
    )


def test_direction_conflict_receives_larger_explicit_penalty() -> None:
    scored = score_candidates(
        (
            _candidate(
                StrategyType.BREAKOUT_CONTINUATION,
                direction=TradeDirection.SHORT,
            ),
        ),
        config=DEFAULT_SCORING_CONFIG,
    )

    adjusted = apply_environment_route_alignment(scored, route=_route())

    assert adjusted[0].final_score == scored[0].final_score
    assert rank_penalty_score(adjusted[0]) == pytest.approx(12.8)
    assert adjusted[0].environment_route_alignment is not None
    assert (
        adjusted[0].environment_route_alignment.state
        is EnvironmentRouteAlignmentState.DIRECTION_CONFLICT
    )
    assert "PREFERRED_DIRECTION_CONFLICT" in (adjusted[0].environment_route_alignment.reason_codes)


def test_explicitly_blocked_environment_is_terminal_and_diagnostic() -> None:
    scored = score_candidates(
        (_candidate(StrategyType.BREAKOUT_CONTINUATION),),
        config=DEFAULT_SCORING_CONFIG,
    )
    route = _route(
        allowed_strategies=(),
        blocked_strategies=tuple(StrategyType),
        preferred_direction=PreferredDirection.NONE,
        strategy_priority=(),
        routing_score=0.0,
        reason_codes=("ENVIRONMENT_ROUTE_BLOCKED",),
        reasons=("environment blocked",),
    )

    adjusted = apply_environment_route_alignment(scored, route=route)

    assert adjusted[0].final_score == 0.0
    assert adjusted[0].environment_route_alignment is not None
    assert adjusted[0].environment_route_alignment.state is EnvironmentRouteAlignmentState.BLOCKED
    assert "CANDIDATE_ENVIRONMENT_BLOCKED" in (adjusted[0].environment_route_alignment.reason_codes)


def test_soft_route_preference_cannot_turn_valid_candidate_into_rejection() -> None:
    candidate = _candidate(
        StrategyType.BREAKOUT_CONTINUATION,
        direction=TradeDirection.SHORT,
    )
    analysis = StrategyAnalysisResult(
        symbol="BTC/USDT",
        decision_time=NOW,
        candidates=(candidate,),
        evaluated_strategies=(StrategyType.BREAKOUT_CONTINUATION,),
    )

    result = analyze_candidate_selection(
        analysis,
        config=ScoringConfig(minimum_accept_score=75.0, warning_accept_score=70.0),
        environment_route=_route(),
    )

    assert result.ranked_candidates[0].final_score == pytest.approx(76.7)
    assert result.ranked_candidates[0].outcome.value == "accepted"
