"""Composite calibration acceptance reporting for existing evidence."""

from __future__ import annotations

from apex.backtesting.calibration_reporting import calibration_reporting_payload
from apex.backtesting.contracts import BacktestReport
from apex.backtesting.drawdown_reporting import (
    drawdown_acceptance_payload,
    evaluate_drawdown_acceptance,
)
from apex.backtesting.evidence_coverage import (
    build_calibration_evidence_coverage,
    calibration_evidence_coverage_payload,
)
from apex.backtesting.partition_reporting import (
    PartitionStabilityReport,
    partition_stability_payload,
)
from apex.backtesting.regime_reporting import (
    RegimeStabilityReport,
    regime_stability_payload,
)


def build_acceptance_reporting_payload(
    report: BacktestReport,
    *,
    partitions: PartitionStabilityReport | None = None,
    regimes: RegimeStabilityReport | None = None,
    maximum_drawdown_limit: float | None = None,
) -> dict[str, object]:
    """Combine existing evidence while preserving fail-closed authority.

    Partition evidence is reported separately from regime evidence. Only the
    explicit regime stability result is passed into the acceptance gate.
    Drawdown is accepted only against an explicit caller-supplied limit.
    """

    stable_regime_performance = regimes.stable_regime_performance if regimes is not None else None
    drawdown = evaluate_drawdown_acceptance(
        report,
        maximum_drawdown_limit=maximum_drawdown_limit,
    )
    calibration = calibration_reporting_payload(
        report,
        acceptable_drawdown=drawdown.acceptable_drawdown,
        stable_regime_performance=stable_regime_performance,
    )

    acceptance = calibration["acceptance"]
    if not isinstance(acceptance, dict):
        raise TypeError("calibration acceptance payload must be a mapping")

    metrics = calibration["metrics"]
    if not isinstance(metrics, dict):
        raise TypeError("calibration metrics payload must be a mapping")

    return {
        "metrics": metrics,
        "acceptance": acceptance,
        "partitions": (partition_stability_payload(partitions) if partitions is not None else None),
        "regimes": regime_stability_payload(regimes) if regimes is not None else None,
        "drawdown": drawdown_acceptance_payload(drawdown),
        "evidence_coverage": calibration_evidence_coverage_payload(
            build_calibration_evidence_coverage(set(metrics))
        ),
        "calibration_authoritative": bool(calibration["calibration_authoritative"]),
    }


__all__ = ["build_acceptance_reporting_payload"]
