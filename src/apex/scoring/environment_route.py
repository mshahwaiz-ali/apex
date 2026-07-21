"""Apply market-environment route context as a soft ranking preference."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from apex.scoring.contracts import (
    EnvironmentRouteAlignment,
    EnvironmentRouteAlignmentState,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.strategies import StrategyType, TradeDirection

_MAX_PRIORITY_PENALTY = 6.0
_MAX_DIRECTION_PENALTY = 16.0
_MAX_WARNING_PENALTY = 4.0
_BLOCKED_ENVIRONMENT_PENALTY = 100.0


class EnvironmentRoute(Protocol):
    """Read-only route contract consumed without coupling scoring to application code."""

    @property
    def allowed_strategies(self) -> Sequence[StrategyType]: ...

    @property
    def blocked_strategies(self) -> Sequence[StrategyType]: ...

    @property
    def preferred_direction(self) -> object: ...

    @property
    def strategy_priority(self) -> Sequence[StrategyType]: ...

    @property
    def routing_score(self) -> float: ...

    @property
    def reason_codes(self) -> Sequence[str]: ...

    @property
    def reasons(self) -> Sequence[str]: ...


def apply_environment_route_alignment(
    candidates: tuple[ScoredCandidate, ...],
    *,
    route: EnvironmentRoute | None,
) -> tuple[ScoredCandidate, ...]:
    """Attach route alignment and apply only bounded, transparent penalties."""

    if route is None:
        return candidates
    return tuple(_adjust_candidate(item, route=route) for item in candidates)


def _adjust_candidate(
    item: ScoredCandidate,
    *,
    route: EnvironmentRoute,
) -> ScoredCandidate:
    preferred_direction = str(
        getattr(route.preferred_direction, "value", route.preferred_direction)
    )
    route_priority = _priority(route.strategy_priority, item.candidate.strategy)
    reason_codes: list[str] = []
    reasons: list[str] = []
    penalty = 0.0

    if "ENVIRONMENT_ROUTE_BLOCKED" in route.reason_codes:
        state = EnvironmentRouteAlignmentState.BLOCKED
        penalty = _BLOCKED_ENVIRONMENT_PENALTY
        reason_codes.append("CANDIDATE_ENVIRONMENT_BLOCKED")
        reasons.append("Market environment is explicitly untradeable for new candidates")
    else:
        state = EnvironmentRouteAlignmentState.ALIGNED
        if route_priority is None:
            state = EnvironmentRouteAlignmentState.LOWER_PRIORITY
            penalty += _MAX_PRIORITY_PENALTY
            reason_codes.append("STRATEGY_OUTSIDE_ROUTE_PRIORITY")
            reasons.append("Strategy remains viable but is outside the environment preference list")
        elif route_priority > 1:
            state = EnvironmentRouteAlignmentState.LOWER_PRIORITY
            priority_penalty = min(_MAX_PRIORITY_PENALTY, (route_priority - 1) * 2.0)
            penalty += priority_penalty
            reason_codes.append("LOWER_ROUTE_PRIORITY")
            reasons.append(f"Strategy is environment route priority {route_priority}")
        else:
            reason_codes.append("CANONICAL_ROUTE_ALIGNMENT")
            reasons.append("Strategy is the canonical environment route preference")

        if _direction_conflicts(preferred_direction, item.candidate.direction):
            state = EnvironmentRouteAlignmentState.DIRECTION_CONFLICT
            direction_penalty = (
                _MAX_DIRECTION_PENALTY * max(0.0, min(100.0, route.routing_score)) / 100.0
            )
            penalty += direction_penalty
            reason_codes.append("PREFERRED_DIRECTION_CONFLICT")
            reasons.append(
                "Candidate direction conflicts with preferred "
                f"{preferred_direction} environment direction"
            )

        warning_penalty = _warning_penalty(route.reason_codes)
        if warning_penalty > 0.0:
            penalty += warning_penalty
            reason_codes.append("ENVIRONMENT_ROUTE_WARNING")
            reasons.append("Conflict, extension, or volatility warnings reduced route confidence")

    penalty = round(min(_BLOCKED_ENVIRONMENT_PENALTY, penalty), 6)
    alignment = EnvironmentRouteAlignment(
        state=state,
        route_priority=route_priority,
        preferred_direction=preferred_direction,
        routing_score=route.routing_score,
        score_adjustment=-penalty,
        reason_codes=tuple(dict.fromkeys(reason_codes)),
        reasons=tuple(dict.fromkeys(reasons)),
    )
    if penalty < _BLOCKED_ENVIRONMENT_PENALTY:
        return ScoredCandidate(
            candidate_id=item.candidate_id,
            candidate=item.candidate,
            breakdown=item.breakdown,
            normalized_metrics=item.normalized_metrics,
            notes=(
                item.notes
                if penalty == 0.0
                else (*item.notes, "market environment route ranking preference attached")
            ),
            environment_route_alignment=alignment,
        )

    # An explicitly blocked environment is a hard rejection. All other route
    # differences are ranking preferences and must not lower the approval score.
    penalty_points = dict(item.breakdown.penalty_points)
    penalty_points["environment_route_alignment"] = penalty
    total_penalty = item.breakdown.total_penalty + penalty
    final_score = max(0.0, min(100.0, item.breakdown.base_score - total_penalty))
    return ScoredCandidate(
        candidate_id=item.candidate_id,
        candidate=item.candidate,
        breakdown=ScoreBreakdown(
            quality_points=item.breakdown.quality_points,
            penalty_points=penalty_points,
            base_score=item.breakdown.base_score,
            total_penalty=total_penalty,
            final_score=final_score,
        ),
        normalized_metrics=item.normalized_metrics,
        notes=(*item.notes, "market environment route alignment applied"),
        environment_route_alignment=alignment,
    )


def _priority(
    priority: Sequence[StrategyType],
    strategy: StrategyType,
) -> int | None:
    try:
        return tuple(priority).index(strategy) + 1
    except ValueError:
        return None


def _direction_conflicts(preferred_direction: str, direction: TradeDirection) -> bool:
    return preferred_direction in {"long", "short"} and direction.value != preferred_direction


def _warning_penalty(reason_codes: Sequence[str]) -> float:
    warning_codes = {
        "ENVIRONMENT_TRADEABILITY_WARNING",
        "ROUTE_CONFLICT_PENALTY",
        "CHASE_STRATEGIES_BLOCKED",
        "EXTREME_VOLATILITY_ROUTE_REDUCTION",
        "SQUEEZE_DIRECTION_UNCONFIRMED",
    }
    count = len(warning_codes.intersection(reason_codes))
    return min(_MAX_WARNING_PENALTY, count * 2.0)
