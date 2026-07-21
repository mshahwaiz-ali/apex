"""Deterministic routing for fresh, mature, exhausted, and reversal-watch states."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.strategies.continuation_freshness import (
    ContinuationFreshness,
    ContinuationState,
)
from apex.strategies.reversal_watch import ReversalWatch, ReversalWatchState


class ContinuationRoute(StrEnum):
    """Permitted strategy route after continuation freshness analysis."""

    CONTINUATION_ALLOWED = "continuation_allowed"
    CONDITIONAL_CONTINUATION = "conditional_continuation"
    NO_NEW_CONTINUATION = "no_new_continuation"
    REVERSAL_WATCH = "reversal_watch"
    REVERSAL_TRIGGERED = "reversal_triggered"


@dataclass(frozen=True, slots=True)
class ContinuationRoutingDecision:
    """One routing decision that never creates a trade by itself."""

    route: ContinuationRoute
    continuation_allowed: bool
    current_execution_allowed: bool
    reversal_candidate_allowed: bool
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.current_execution_allowed and not self.continuation_allowed:
            raise ValueError("current continuation execution requires continuation permission")
        if (
            self.reversal_candidate_allowed
            and self.route is not ContinuationRoute.REVERSAL_TRIGGERED
        ):
            raise ValueError("reversal candidate permission requires a triggered reversal route")
        if not self.rationale:
            raise ValueError("continuation routing requires rationale")


def route_continuation(
    *,
    freshness: ContinuationFreshness,
    reversal_watch: ReversalWatch | None = None,
) -> ContinuationRoutingDecision:
    """Route continuation and reversal evidence without bypassing confirmation."""

    if freshness.state in {
        ContinuationState.FRESH_BREAK,
        ContinuationState.FIRST_CONTINUATION,
    }:
        return ContinuationRoutingDecision(
            route=ContinuationRoute.CONTINUATION_ALLOWED,
            continuation_allowed=True,
            current_execution_allowed=True,
            reversal_candidate_allowed=False,
            rationale=freshness.reasons,
        )

    if freshness.state is ContinuationState.MATURE_CONTINUATION:
        return ContinuationRoutingDecision(
            route=ContinuationRoute.CONDITIONAL_CONTINUATION,
            continuation_allowed=True,
            current_execution_allowed=False,
            reversal_candidate_allowed=False,
            rationale=(
                *freshness.reasons,
                "mature continuation requires pullback or renewed confirmation",
            ),
        )

    if reversal_watch is None or reversal_watch.state is ReversalWatchState.NONE:
        return ContinuationRoutingDecision(
            route=ContinuationRoute.NO_NEW_CONTINUATION,
            continuation_allowed=False,
            current_execution_allowed=False,
            reversal_candidate_allowed=False,
            rationale=(
                *freshness.reasons,
                "exhausted move blocks a new continuation entry",
                "no opposite-direction reversal evidence is confirmed",
            ),
        )

    if reversal_watch.state is ReversalWatchState.WATCH:
        return ContinuationRoutingDecision(
            route=ContinuationRoute.REVERSAL_WATCH,
            continuation_allowed=False,
            current_execution_allowed=False,
            reversal_candidate_allowed=False,
            rationale=(
                *freshness.reasons,
                *reversal_watch.reasons,
                "reversal remains watch-only until reclaim confirmation completes",
            ),
        )

    return ContinuationRoutingDecision(
        route=ContinuationRoute.REVERSAL_TRIGGERED,
        continuation_allowed=False,
        current_execution_allowed=False,
        reversal_candidate_allowed=True,
        rationale=(
            *freshness.reasons,
            *reversal_watch.reasons,
            "reversal trigger is complete; a reversal strategy may evaluate a candidate",
        ),
    )


__all__ = [
    "ContinuationRoute",
    "ContinuationRoutingDecision",
    "route_continuation",
]
