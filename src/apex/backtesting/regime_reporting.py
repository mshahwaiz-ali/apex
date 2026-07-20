"""Regime stability reporting for existing backtest aggregates."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apex.backtesting.contracts import BacktestReport


@dataclass(frozen=True, slots=True)
class RegimePerformance:
    """Metrics already produced for one named market regime."""

    regime: str
    sample_size: int
    expectancy: float
    profit_factor: float | None
    average_r: float
    maximum_drawdown: float
    positive_expectancy: bool

    def __post_init__(self) -> None:
        if not self.regime.strip():
            raise ValueError("regime name cannot be empty")
        if self.sample_size < 0:
            raise ValueError("regime sample size cannot be negative")


@dataclass(frozen=True, slots=True)
class RegimeStabilityReport:
    """Fail-closed evidence summary across named market regimes."""

    regimes: tuple[RegimePerformance, ...]
    regime_count: int
    sampled_regime_count: int
    all_regimes_sampled: bool
    all_expectancies_positive: bool | None
    expectancy_spread: float | None
    stable_regime_performance: bool | None
    blockers: tuple[str, ...]
    calibration_authoritative: bool = False

    def __post_init__(self) -> None:
        if self.calibration_authoritative:
            raise ValueError("regime reporting cannot make calibration authoritative by itself")
        if self.regime_count != len(self.regimes):
            raise ValueError("regime count must match reported regimes")
        expected_sampled = sum(regime.sample_size > 0 for regime in self.regimes)
        if self.sampled_regime_count != expected_sampled:
            raise ValueError("sampled regime count must match regime evidence")
        expected_all_sampled = bool(self.regimes) and expected_sampled == len(self.regimes)
        if self.all_regimes_sampled is not expected_all_sampled:
            raise ValueError("all-regimes-sampled gate must match regime evidence")
        if len(set(self.blockers)) != len(self.blockers):
            raise ValueError("regime stability blockers must be unique")


def build_regime_stability_report(
    reports: Mapping[str, BacktestReport],
    *,
    minimum_regime_count: int = 2,
) -> RegimeStabilityReport:
    """Summarize existing regime reports without inventing thresholds.

    Stability remains unavailable until at least ``minimum_regime_count`` named
    regimes are present and each regime has at least one simulated trade.
    """

    if minimum_regime_count < 1:
        raise ValueError("minimum regime count must be positive")

    regimes = tuple(
        _regime_performance(name, report)
        for name, report in sorted(reports.items(), key=lambda item: item[0])
    )
    regime_count = len(regimes)
    sampled_count = sum(regime.sample_size > 0 for regime in regimes)
    all_sampled = bool(regimes) and sampled_count == regime_count

    blockers: list[str] = []
    if regime_count < minimum_regime_count:
        blockers.append("insufficient_regime_coverage")
    if not all_sampled:
        blockers.append("regime_samples_incomplete")

    all_positive: bool | None
    spread: float | None
    stable: bool | None
    if blockers:
        all_positive = None
        spread = None
        stable = None
    else:
        expectancies = tuple(regime.expectancy for regime in regimes)
        all_positive = all(value > 0.0 for value in expectancies)
        spread = max(expectancies) - min(expectancies)
        stable = all_positive

    return RegimeStabilityReport(
        regimes=regimes,
        regime_count=regime_count,
        sampled_regime_count=sampled_count,
        all_regimes_sampled=all_sampled,
        all_expectancies_positive=all_positive,
        expectancy_spread=spread,
        stable_regime_performance=stable,
        blockers=tuple(sorted(blockers)),
    )


def regime_stability_payload(report: RegimeStabilityReport) -> dict[str, object]:
    """Return deterministic serializable regime evidence."""

    return {
        "regimes": [
            {
                "regime": regime.regime,
                "sample_size": regime.sample_size,
                "expectancy": regime.expectancy,
                "profit_factor": regime.profit_factor,
                "average_r": regime.average_r,
                "maximum_drawdown": regime.maximum_drawdown,
                "positive_expectancy": regime.positive_expectancy,
            }
            for regime in report.regimes
        ],
        "regime_count": report.regime_count,
        "sampled_regime_count": report.sampled_regime_count,
        "all_regimes_sampled": report.all_regimes_sampled,
        "all_expectancies_positive": report.all_expectancies_positive,
        "expectancy_spread": report.expectancy_spread,
        "stable_regime_performance": report.stable_regime_performance,
        "blockers": list(report.blockers),
        "calibration_authoritative": report.calibration_authoritative,
    }


def _regime_performance(name: str, report: BacktestReport) -> RegimePerformance:
    return RegimePerformance(
        regime=name,
        sample_size=report.total_trades,
        expectancy=report.expectancy,
        profit_factor=report.profit_factor,
        average_r=report.average_risk_reward,
        maximum_drawdown=report.maximum_drawdown,
        positive_expectancy=report.expectancy > 0.0,
    )


__all__ = [
    "RegimePerformance",
    "RegimeStabilityReport",
    "build_regime_stability_report",
    "regime_stability_payload",
]
