"""Interpret canonical trade-management plans without claiming live execution."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from apex.application.methodology_management_contracts import ManagementActionType
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ManagementSemantics:
    """Truthful lifecycle coverage and allocation semantics."""

    plan_available: bool
    step_count: int
    partial_exit_count: int
    partial_close_total_percentage: float
    partial_allocation_complete: bool
    breakeven_available: bool
    trailing_available: bool
    time_exit_available: bool
    momentum_failure_exit_available: bool
    lifecycle_execution_state_available: bool
    interpretation: str
    limitations: tuple[str, ...]


def derive_management_semantics(
    methodology: MethodologySnapshot,
) -> ManagementSemantics:
    """Summarize management instructions while keeping trigger state unresolved."""

    steps = methodology.management_steps
    kinds = {step.kind for step in steps}
    partials = tuple(step for step in steps if step.kind is ManagementActionType.PARTIAL_EXIT)
    partial_total = sum(step.close_percentage or 0.0 for step in partials)
    allocation_complete = bool(partials) and math.isclose(
        partial_total,
        100.0,
        rel_tol=0.0,
        abs_tol=1e-9,
    )

    if not steps:
        interpretation = "no canonical trade-management plan is available"
    elif allocation_complete:
        interpretation = (
            "canonical management instructions include a complete partial-exit allocation; "
            "protective actions remain conditional on their stated triggers"
        )
    else:
        interpretation = (
            "canonical management instructions are available, but partial-exit allocation does "
            "not account for the entire position"
        )

    return ManagementSemantics(
        plan_available=bool(steps),
        step_count=len(steps),
        partial_exit_count=len(partials),
        partial_close_total_percentage=partial_total,
        partial_allocation_complete=allocation_complete,
        breakeven_available=ManagementActionType.BREAKEVEN in kinds,
        trailing_available=ManagementActionType.TRAILING in kinds,
        time_exit_available=ManagementActionType.TIME_EXIT in kinds,
        momentum_failure_exit_available=(ManagementActionType.MOMENTUM_FAILURE in kinds),
        lifecycle_execution_state_available=False,
        interpretation=interpretation,
        limitations=(
            "management instructions describe policy and do not prove that any trigger has fired",
            "open quantity, fills, realized partials, and current stop state are not "
            "part of the methodology snapshot",
            "breakeven and trailing actions require explicit trigger evaluation during "
            "paper or live lifecycle processing",
        ),
    )


def management_semantics_payload(semantics: ManagementSemantics) -> dict[str, Any]:
    """Serialize canonical management-plan interpretation."""

    return {
        "plan_available": semantics.plan_available,
        "step_count": semantics.step_count,
        "partial_exit_count": semantics.partial_exit_count,
        "partial_close_total_percentage": semantics.partial_close_total_percentage,
        "partial_allocation_complete": semantics.partial_allocation_complete,
        "breakeven_available": semantics.breakeven_available,
        "trailing_available": semantics.trailing_available,
        "time_exit_available": semantics.time_exit_available,
        "momentum_failure_exit_available": semantics.momentum_failure_exit_available,
        "lifecycle_execution_state_available": (semantics.lifecycle_execution_state_available),
        "interpretation": semantics.interpretation,
        "limitations": list(semantics.limitations),
    }


__all__ = [
    "ManagementSemantics",
    "derive_management_semantics",
    "management_semantics_payload",
]
