"""Shadow-only payoff experiments over existing structural geometry."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PayoffExperiment(StrEnum):
    CANONICAL = "canonical"
    CONFIRMATION_OR_RETEST_ENTRY = "confirmation_or_retest_entry"
    NO_CHASE = "no_chase"
    TP1_FULL_EXIT = "tp1_full_exit"
    TP1_PARTIAL_BREAKEVEN_RUNNER = "tp1_partial_breakeven_runner"
    HIGHER_COST_STRESS = "higher_cost_stress"
    DELAYED_FILL_STRESS = "delayed_fill_stress"


@dataclass(frozen=True, slots=True)
class PayoffObservation:
    candidate_id: str
    canonical_net_r: float
    tp1_net_r: float
    runner_net_r: float | None
    confirmation_or_retest_filled: bool
    chased: bool
    higher_cost_delta_r: float
    delayed_fill_delta_r: float


@dataclass(frozen=True, slots=True)
class PayoffShadowResult:
    experiment: PayoffExperiment
    candidate_id: str
    included: bool
    net_r: float | None
    authority: str = "shadow_only"


def evaluate_payoff_shadows(
    observation: PayoffObservation,
    *,
    tp1_partial_fraction: float = 0.50,
) -> tuple[PayoffShadowResult, ...]:
    """Compare execution/management without changing canonical lifecycle metrics."""

    if not 0.0 <= tp1_partial_fraction <= 1.0:
        raise ValueError("TP1 partial fraction must be in the unit interval")
    runner = observation.runner_net_r if observation.runner_net_r is not None else 0.0
    partial_runner = observation.tp1_net_r * tp1_partial_fraction + runner * (
        1.0 - tp1_partial_fraction
    )
    return (
        PayoffShadowResult(
            PayoffExperiment.CANONICAL,
            observation.candidate_id,
            True,
            observation.canonical_net_r,
        ),
        PayoffShadowResult(
            PayoffExperiment.CONFIRMATION_OR_RETEST_ENTRY,
            observation.candidate_id,
            observation.confirmation_or_retest_filled,
            (observation.canonical_net_r if observation.confirmation_or_retest_filled else None),
        ),
        PayoffShadowResult(
            PayoffExperiment.NO_CHASE,
            observation.candidate_id,
            not observation.chased,
            observation.canonical_net_r if not observation.chased else None,
        ),
        PayoffShadowResult(
            PayoffExperiment.TP1_FULL_EXIT,
            observation.candidate_id,
            True,
            observation.tp1_net_r,
        ),
        PayoffShadowResult(
            PayoffExperiment.TP1_PARTIAL_BREAKEVEN_RUNNER,
            observation.candidate_id,
            True,
            partial_runner,
        ),
        PayoffShadowResult(
            PayoffExperiment.HIGHER_COST_STRESS,
            observation.candidate_id,
            True,
            observation.canonical_net_r - abs(observation.higher_cost_delta_r),
        ),
        PayoffShadowResult(
            PayoffExperiment.DELAYED_FILL_STRESS,
            observation.candidate_id,
            True,
            observation.canonical_net_r - abs(observation.delayed_fill_delta_r),
        ),
    )


def attempted_payoff_configurations(results: tuple[PayoffShadowResult, ...]) -> int:
    """Return the comparison population that must be included in DSR/PBO."""

    return len({result.experiment for result in results})


__all__ = [
    "PayoffExperiment",
    "PayoffObservation",
    "PayoffShadowResult",
    "attempted_payoff_configurations",
    "evaluate_payoff_shadows",
]
