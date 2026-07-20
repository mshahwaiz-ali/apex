"""Calibration acceptance policy for Apex methodology claims."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum

from apex.backtesting.calibration_metrics import CalibrationReport


class AcceptanceState(StrEnum):
    """Whether calibration permits user-facing reliability claims."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    INSUFFICIENT_SAMPLE = "insufficient_sample"


@dataclass(frozen=True, slots=True)
class CalibrationAcceptancePolicy:
    """Explicit thresholds for calibrated methodology acceptance."""

    minimum_counted_trades: int = 100
    minimum_expectancy_r: float = 0.0
    minimum_profit_factor: float = 1.0
    maximum_false_cmp_signal_rate: float = 0.25
    maximum_stop_rate: float = 0.60
    maximum_margin_failure_rate: float = 0.0
    minimum_regime_trades: int = 20
    minimum_stable_regime_fraction: float = 0.60

    def __post_init__(self) -> None:
        if self.minimum_counted_trades <= 0:
            raise ValueError("minimum counted trades must be positive")
        if self.minimum_regime_trades <= 0:
            raise ValueError("minimum regime trades must be positive")
        for name in (
            "minimum_expectancy_r",
            "minimum_profit_factor",
            "maximum_false_cmp_signal_rate",
            "maximum_stop_rate",
            "maximum_margin_failure_rate",
            "minimum_stable_regime_fraction",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite")
        for name in (
            "maximum_false_cmp_signal_rate",
            "maximum_stop_rate",
            "maximum_margin_failure_rate",
            "minimum_stable_regime_fraction",
        ):
            value = float(getattr(self, name))
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class CalibrationAcceptanceResult:
    """Truthful acceptance decision and all blocking reasons."""

    state: AcceptanceState
    reasons: tuple[str, ...]
    confidence_claims_allowed: bool
    stable_regime_fraction: float | None


def evaluate_calibration_acceptance(
    report: CalibrationReport,
    *,
    policy: CalibrationAcceptancePolicy,
) -> CalibrationAcceptanceResult:
    """Apply precision, expectancy, and stability gates."""

    overall = report.overall
    if overall.counted_trades < policy.minimum_counted_trades:
        return CalibrationAcceptanceResult(
            state=AcceptanceState.INSUFFICIENT_SAMPLE,
            reasons=(
                f"counted sample {overall.counted_trades} is below "
                f"minimum {policy.minimum_counted_trades}",
            ),
            confidence_claims_allowed=False,
            stable_regime_fraction=None,
        )

    reasons: list[str] = []
    if overall.expectancy_r is None or overall.expectancy_r <= policy.minimum_expectancy_r:
        reasons.append("expectancy is not above the configured minimum")
    if overall.profit_factor is None or overall.profit_factor < policy.minimum_profit_factor:
        reasons.append("profit factor is below the configured minimum")
    if (
        overall.false_cmp_signal_rate is None
        or overall.false_cmp_signal_rate > policy.maximum_false_cmp_signal_rate
    ):
        reasons.append("false CMP signal rate exceeds the configured maximum")
    if overall.stop_rate is None or overall.stop_rate > policy.maximum_stop_rate:
        reasons.append("stop rate exceeds the configured maximum")
    if (
        overall.liquidation_or_margin_failure_rate is None
        or overall.liquidation_or_margin_failure_rate > policy.maximum_margin_failure_rate
    ):
        reasons.append("liquidation or margin failure rate exceeds the configured maximum")

    eligible_regimes = tuple(
        item
        for item in report.by_regime
        if item.metrics.counted_trades >= policy.minimum_regime_trades
    )
    stable_regimes = tuple(
        item
        for item in eligible_regimes
        if item.metrics.expectancy_r is not None
        and item.metrics.expectancy_r > policy.minimum_expectancy_r
    )
    stable_fraction = len(stable_regimes) / len(eligible_regimes) if eligible_regimes else None
    if stable_fraction is None:
        reasons.append("no regime has enough samples for stability evaluation")
    elif stable_fraction < policy.minimum_stable_regime_fraction:
        reasons.append("stable regime fraction is below the configured minimum")

    accepted = not reasons
    return CalibrationAcceptanceResult(
        state=AcceptanceState.ACCEPTED if accepted else AcceptanceState.REJECTED,
        reasons=tuple(reasons),
        confidence_claims_allowed=accepted,
        stable_regime_fraction=stable_fraction,
    )


__all__ = [
    "AcceptanceState",
    "CalibrationAcceptancePolicy",
    "CalibrationAcceptanceResult",
    "evaluate_calibration_acceptance",
]
