"""Map canonical candidate and context facts into execution quality."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate, TradeDirection
from apex.strategies.execution_quality import (
    CappedExecutionQualityResult,
    ExecutionQualityConstraints,
    ExecutionQualityInputs,
    apply_execution_quality_caps,
    calculate_execution_quality,
)


@dataclass(frozen=True, slots=True)
class CandidateExecutionQuality:
    """Candidate-level execution-quality result and normalized inputs."""

    inputs: ExecutionQualityInputs
    constraints: ExecutionQualityConstraints
    result: CappedExecutionQualityResult


def evaluate_candidate_execution_quality(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
) -> CandidateExecutionQuality:
    """Evaluate execution quality from canonical candidate and decision-frame facts."""

    frame = context.decision_frame
    current = candidate.entry.current_price
    inside_entry_zone = candidate.entry.lower <= current <= candidate.entry.upper
    chase_limit_violated = _chase_limit_violated(candidate)
    stop_feasible = _stop_feasible(candidate, context)
    trigger_complete = candidate.metadata.get("entry_confirmation_complete") is True
    spread = _effective_spread_percentage(context)
    spread_available = spread is not None

    inputs = ExecutionQualityInputs(
        location=candidate.entry.location_quality,
        trigger_completion=1.0 if trigger_complete else 0.0,
        freshness=_freshness_score(candidate),
        spread_slippage=_spread_slippage_score(spread),
        stop_feasibility=_stop_feasibility_score(candidate, context),
        chase_safety=0.0 if chase_limit_violated else _chase_safety_score(candidate),
        data_quality=frame.data_confidence,
    )
    constraints = ExecutionQualityConstraints(
        provisional_evidence=candidate.provisional or context.provisional,
        trigger_complete=trigger_complete,
        data_stale=frame.is_stale,
        data_degraded=frame.data_confidence < 0.75,
        inside_entry_zone=inside_entry_zone,
        chase_limit_violated=chase_limit_violated,
        stop_feasible=stop_feasible,
        spread_slippage_available=spread_available,
    )
    raw = calculate_execution_quality(inputs)
    capped = apply_execution_quality_caps(raw, constraints)
    return CandidateExecutionQuality(
        inputs=inputs,
        constraints=constraints,
        result=capped,
    )


def attach_candidate_execution_quality(
    *,
    candidate: TradeCandidate,
    context: StrategyContext,
) -> TradeCandidate:
    """Return a frozen candidate copy with truthful execution-quality authority."""

    evaluated = evaluate_candidate_execution_quality(
        candidate=candidate,
        context=context,
    )
    result = evaluated.result
    score_dimensions = replace(
        candidate.score_dimensions,
        execution_quality=result.final_score * 100.0,
    )
    metadata = {
        **candidate.metadata,
        "execution_quality_uncapped": result.uncapped_score * 100.0,
        "execution_quality_cap": result.applied_cap * 100.0,
        "execution_quality_final": result.final_score * 100.0,
        "execution_quality_capped": result.applied_cap < 1.0,
        "execution_quality_cap_reasons": " | ".join(result.cap_reasons),
    }
    return replace(
        candidate,
        score_dimensions=score_dimensions,
        metadata=metadata,
    )


def _freshness_score(candidate: TradeCandidate) -> float:
    state = candidate.metadata.get("continuation_state")
    if state == "fresh_break":
        return 1.0
    if state == "first_continuation":
        return 0.85
    if state == "mature_continuation":
        return 0.45
    if state == "exhausted":
        return 0.0
    return max(0.0, 1.0 - candidate.quality.extension_penalty)


def _effective_spread_percentage(context: StrategyContext) -> float | None:
    frame = context.decision_frame
    values = tuple(
        value
        for value in (
            frame.spread_percentage,
            frame.order_book_spread_percentage,
        )
        if value is not None
    )
    return max(values) if values else None


def _spread_slippage_score(spread_percentage: float | None) -> float:
    if spread_percentage is None:
        return 0.5
    if spread_percentage <= 0.05:
        return 1.0
    if spread_percentage >= 0.25:
        return 0.0
    return 1.0 - (spread_percentage - 0.05) / 0.20


def _stop_feasible(candidate: TradeCandidate, context: StrategyContext) -> bool:
    stop_distance = abs(candidate.entry.preferred - candidate.invalidation.price)
    return stop_distance > 0.0 and stop_distance <= context.atr * 4.0


def _stop_feasibility_score(
    candidate: TradeCandidate,
    context: StrategyContext,
) -> float:
    stop_atr = abs(candidate.entry.preferred - candidate.invalidation.price) / context.atr
    if stop_atr <= 0.0 or stop_atr > 4.0:
        return 0.0
    if 0.30 <= stop_atr <= 2.0:
        return 1.0
    if stop_atr < 0.30:
        return stop_atr / 0.30
    return max(0.0, 1.0 - (stop_atr - 2.0) / 2.0)


def _chase_limit_violated(candidate: TradeCandidate) -> bool:
    limit = candidate.entry.max_chase_price
    if limit is None:
        return False
    current = candidate.entry.current_price
    if candidate.direction is TradeDirection.LONG:
        return current > limit
    return current < limit


def _chase_safety_score(candidate: TradeCandidate) -> float:
    if candidate.entry.is_extended:
        return 0.0
    return max(0.0, 1.0 - candidate.entry.atr_distance)


__all__ = [
    "CandidateExecutionQuality",
    "attach_candidate_execution_quality",
    "evaluate_candidate_execution_quality",
]
