"""Explicit drawdown acceptance policy for existing backtest reports."""

from __future__ import annotations

import math
from dataclasses import dataclass

from apex.backtesting.contracts import BacktestReport


@dataclass(frozen=True, slots=True)
class DrawdownAcceptanceReport:
    """Evaluate maximum drawdown only against an explicit caller policy."""

    observed_maximum_drawdown: float
    maximum_drawdown_limit: float | None
    acceptable_drawdown: bool | None
    blocker: str | None

    def __post_init__(self) -> None:
        if not math.isfinite(self.observed_maximum_drawdown):
            raise ValueError("observed maximum drawdown must be finite")
        if self.observed_maximum_drawdown < 0.0:
            raise ValueError("observed maximum drawdown cannot be negative")
        if self.maximum_drawdown_limit is not None:
            if not math.isfinite(self.maximum_drawdown_limit):
                raise ValueError("maximum drawdown limit must be finite")
            if self.maximum_drawdown_limit < 0.0:
                raise ValueError("maximum drawdown limit cannot be negative")

        expected = (
            None
            if self.maximum_drawdown_limit is None
            else self.observed_maximum_drawdown <= self.maximum_drawdown_limit
        )
        if self.acceptable_drawdown is not expected:
            raise ValueError("drawdown acceptance must match observed evidence and policy")
        expected_blocker = (
            "drawdown_policy_unavailable"
            if self.maximum_drawdown_limit is None
            else None
            if expected
            else "drawdown_exceeds_limit"
        )
        if self.blocker != expected_blocker:
            raise ValueError("drawdown blocker must match acceptance evidence")


def evaluate_drawdown_acceptance(
    report: BacktestReport,
    *,
    maximum_drawdown_limit: float | None,
) -> DrawdownAcceptanceReport:
    """Evaluate existing drawdown without selecting or tuning the threshold."""

    acceptable = (
        None
        if maximum_drawdown_limit is None
        else report.maximum_drawdown <= maximum_drawdown_limit
    )
    blocker = (
        "drawdown_policy_unavailable"
        if maximum_drawdown_limit is None
        else None
        if acceptable
        else "drawdown_exceeds_limit"
    )
    return DrawdownAcceptanceReport(
        observed_maximum_drawdown=report.maximum_drawdown,
        maximum_drawdown_limit=maximum_drawdown_limit,
        acceptable_drawdown=acceptable,
        blocker=blocker,
    )


def drawdown_acceptance_payload(
    report: DrawdownAcceptanceReport,
) -> dict[str, object]:
    return {
        "observed_maximum_drawdown": report.observed_maximum_drawdown,
        "maximum_drawdown_limit": report.maximum_drawdown_limit,
        "acceptable_drawdown": report.acceptable_drawdown,
        "blocker": report.blocker,
    }


__all__ = [
    "DrawdownAcceptanceReport",
    "drawdown_acceptance_payload",
    "evaluate_drawdown_acceptance",
]
