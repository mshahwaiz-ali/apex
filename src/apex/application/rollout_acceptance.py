"""Deterministic, non-authoritative rollout acceptance policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.rollout_comparison import AnalysisComparisonSummary


@dataclass(frozen=True, slots=True)
class RolloutAcceptanceResult:
    """Operator-facing acceptance result for rollout diagnostics."""

    accepted: bool
    regression_count: int
    compatibility_only_count: int
    match_count: int
    total_count: int
    reasons: tuple[str, ...]
    authoritative: bool = False
    interpretation: str = (
        "diagnostic rollout acceptance only; this result does not affect "
        "trade selection, ranking, scoring, actionability, or execution"
    )


def evaluate_rollout_acceptance(
    summary: AnalysisComparisonSummary,
) -> RolloutAcceptanceResult:
    """Accept only summaries with zero structural regression candidates."""

    reasons: list[str] = []
    accepted = summary.regression_count == 0

    if summary.regression_count:
        reasons.append(f"{summary.regression_count} structural regression candidate(s) detected")
    else:
        reasons.append("no structural regression candidates detected")

    if summary.compatibility_only_count:
        reasons.append(
            f"{summary.compatibility_only_count} compatibility-only difference set(s) allowed"
        )
    else:
        reasons.append("no compatibility-only differences detected")

    return RolloutAcceptanceResult(
        accepted=accepted,
        regression_count=summary.regression_count,
        compatibility_only_count=summary.compatibility_only_count,
        match_count=summary.match_count,
        total_count=summary.total_count,
        reasons=tuple(reasons),
    )


def rollout_acceptance_payload(
    result: RolloutAcceptanceResult,
) -> dict[str, Any]:
    """Serialize a stable, explicitly non-authoritative acceptance payload."""

    return {
        "accepted": result.accepted,
        "regression_count": result.regression_count,
        "compatibility_only_count": result.compatibility_only_count,
        "match_count": result.match_count,
        "total_count": result.total_count,
        "reasons": list(result.reasons),
        "authoritative": result.authoritative,
        "interpretation": result.interpretation,
    }


__all__ = [
    "RolloutAcceptanceResult",
    "evaluate_rollout_acceptance",
    "rollout_acceptance_payload",
]
