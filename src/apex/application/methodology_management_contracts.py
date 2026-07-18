"""Canonical trade-management contracts for methodology snapshots."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.application.methodology_contracts import TargetRole


class ManagementActionType(StrEnum):
    """Supported lifecycle actions after a trade becomes active."""

    PARTIAL_EXIT = "partial_exit"
    BREAKEVEN = "breakeven"
    TRAILING = "trailing"
    TIME_EXIT = "time_exit"
    MOMENTUM_FAILURE = "momentum_failure"


@dataclass(frozen=True, slots=True)
class ManagementStep:
    """One deterministic management instruction with explicit provenance."""

    kind: ManagementActionType
    trigger: str
    action: str
    rationale: tuple[str, ...]
    target_role: TargetRole | None = None
    close_percentage: float | None = None

    def __post_init__(self) -> None:
        if not self.trigger.strip() or not self.action.strip():
            raise ValueError("management trigger and action cannot be empty")
        if not self.rationale:
            raise ValueError("management rationale cannot be empty")
        if self.close_percentage is not None:
            if not math.isfinite(self.close_percentage):
                raise ValueError("management close percentage must be finite")
            if not 0.0 < self.close_percentage <= 100.0:
                raise ValueError(
                    "management close percentage must be greater than zero and at most 100"
                )
        if self.kind is ManagementActionType.PARTIAL_EXIT:
            if self.target_role is None or self.close_percentage is None:
                raise ValueError(
                    "partial-exit management requires a target role and close percentage"
                )
        elif self.target_role is not None or self.close_percentage is not None:
            raise ValueError(
                "target role and close percentage are reserved for partial-exit management"
            )


__all__ = ["ManagementActionType", "ManagementStep"]
