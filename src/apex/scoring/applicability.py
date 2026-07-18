"""Apply strategy applicability as a transparent candidate-score overlay."""

from __future__ import annotations

from collections.abc import Mapping

from apex.scoring.contracts import ScoreBreakdown, ScoredCandidate
from apex.strategies import (
    StrategyApplicability,
    StrategyApplicabilityState,
    StrategyType,
)

_MAX_APPLICABILITY_PENALTY = 20.0


def apply_strategy_applicability(
    candidates: tuple[ScoredCandidate, ...],
    *,
    applicability: Mapping[StrategyType, StrategyApplicability],
) -> tuple[ScoredCandidate, ...]:
    """Penalize conditional candidates without changing canonical scores."""

    adjusted: list[ScoredCandidate] = []
    for item in candidates:
        record = applicability.get(item.candidate.strategy)
        if record is None:
            adjusted.append(item)
            continue
        if record.state is StrategyApplicabilityState.NOT_APPLICABLE:
            raise ValueError(
                "not-applicable strategy candidate reached candidate scoring: "
                f"{item.candidate.strategy.value}"
            )
        if record.state is StrategyApplicabilityState.APPLICABLE:
            adjusted.append(item)
            continue

        penalty = (100.0 - record.score) / 100.0 * _MAX_APPLICABILITY_PENALTY
        penalty_points = dict(item.breakdown.penalty_points)
        penalty_points["strategy_applicability"] = penalty
        total_penalty = item.breakdown.total_penalty + penalty
        final_score = max(
            0.0,
            min(
                100.0,
                item.breakdown.base_score - total_penalty,
            ),
        )
        adjusted.append(
            ScoredCandidate(
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
                notes=(
                    *item.notes,
                    "conditional strategy applicability penalty applied",
                ),
                environment_route_alignment=item.environment_route_alignment,
            )
        )
    return tuple(adjusted)
