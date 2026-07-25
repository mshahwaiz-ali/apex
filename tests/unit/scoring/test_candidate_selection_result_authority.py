from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.scoring.contracts import (
    CandidateOutcome,
    CandidateSelectionResult,
    ConflictSummary,
    DirectionalConsensus,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 25, tzinfo=UTC)


def _ranked(direction: TradeDirection, candidate_id: str) -> RankedCandidate:
    candidate = SimpleNamespace(direction=direction)
    scored = ScoredCandidate(
        candidate_id=candidate_id,
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points={"setup": 80.0},
            penalty_points={},
            base_score=80.0,
            total_penalty=0.0,
            final_score=80.0,
        ),
        normalized_metrics={},
    )
    return RankedCandidate(
        scored=scored,
        rank=1,
        outcome=CandidateOutcome.ACCEPTED,
        reasons=(),
        tie_break=(),
    )


def _result(
    *,
    selected_candidate: RankedCandidate | None,
    selected_future_candidate: RankedCandidate | None,
) -> CandidateSelectionResult:
    retained = selected_candidate or selected_future_candidate
    assert retained is not None
    return CandidateSelectionResult(
        symbol="BTCUSDT",
        decision_time=NOW,
        all_scored_candidates=(retained.scored,),
        ranked_candidates=(retained,),
        rejected_candidates=(),
        conflict_summary=ConflictSummary(
            directional_consensus=DirectionalConsensus.LONG
            if retained.candidate.direction is TradeDirection.LONG
            else DirectionalConsensus.SHORT,
            long_count=1 if retained.candidate.direction is TradeDirection.LONG else 0,
            short_count=1 if retained.candidate.direction is TradeDirection.SHORT else 0,
            duplicate_groups=(),
            warnings=(),
        ),
        directional_consensus=DirectionalConsensus.LONG
        if retained.candidate.direction is TradeDirection.LONG
        else DirectionalConsensus.SHORT,
        selected_candidate=selected_candidate,
        selected_future_candidate=selected_future_candidate,
        no_trade_reason=None,
        evaluated_strategy_order=(StrategyType.BREAKOUT_CONTINUATION,),
        configuration_id="test",
        metadata={},
    )


def test_selected_direction_uses_current_setup_when_available() -> None:
    current = _ranked(TradeDirection.LONG, "current")

    result = _result(selected_candidate=current, selected_future_candidate=None)

    assert result.selected_setup_candidate is current
    assert result.selected_direction is TradeDirection.LONG


def test_selected_direction_uses_future_setup_when_no_current_setup_exists() -> None:
    future = _ranked(TradeDirection.SHORT, "future")

    result = _result(selected_candidate=None, selected_future_candidate=future)

    assert result.setup_exists
    assert result.selected_setup_candidate is future
    assert result.selected_direction is TradeDirection.SHORT
    assert result.selected_executable_candidate is None
