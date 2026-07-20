"""Chronological partition stability reporting for existing backtests."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from apex.backtesting.contracts import BacktestReport
from apex.backtesting.historical_signal_replay import HistoricalSignalSplit

_REQUIRED_SPLITS = (
    HistoricalSignalSplit.TRAIN,
    HistoricalSignalSplit.VALIDATION,
    HistoricalSignalSplit.FINAL_TEST,
)


@dataclass(frozen=True, slots=True)
class PartitionPerformance:
    """Metrics already produced by one chronological backtest partition."""

    split: HistoricalSignalSplit
    sample_size: int
    expectancy: float
    profit_factor: float | None
    average_r: float
    maximum_drawdown: float
    positive_expectancy: bool


@dataclass(frozen=True, slots=True)
class PartitionStabilityReport:
    """Evidence summary across train, validation, and final-test partitions."""

    partitions: tuple[PartitionPerformance, ...]
    missing_splits: tuple[HistoricalSignalSplit, ...]
    complete: bool
    all_partitions_sampled: bool
    all_expectancies_positive: bool | None
    expectancy_spread: float | None
    calibration_authoritative: bool = False

    def __post_init__(self) -> None:
        if self.calibration_authoritative:
            raise ValueError("partition reporting cannot make calibration authoritative by itself")
        expected_complete = not self.missing_splits
        if self.complete is not expected_complete:
            raise ValueError("partition completeness must match missing splits")
        expected_sampled = self.complete and all(
            partition.sample_size > 0 for partition in self.partitions
        )
        if self.all_partitions_sampled is not expected_sampled:
            raise ValueError("partition sample gate must match partition evidence")


def build_partition_stability_report(
    reports: Mapping[HistoricalSignalSplit, BacktestReport],
) -> PartitionStabilityReport:
    """Summarize existing chronological partition reports without new simulation."""

    partitions = tuple(
        _partition_performance(split, reports[split])
        for split in _REQUIRED_SPLITS
        if split in reports
    )
    missing = tuple(split for split in _REQUIRED_SPLITS if split not in reports)
    complete = not missing
    all_sampled = complete and all(partition.sample_size > 0 for partition in partitions)

    all_positive: bool | None
    expectancy_spread: float | None
    if not all_sampled:
        all_positive = None
        expectancy_spread = None
    else:
        expectancies = tuple(partition.expectancy for partition in partitions)
        all_positive = all(value > 0.0 for value in expectancies)
        expectancy_spread = max(expectancies) - min(expectancies)

    return PartitionStabilityReport(
        partitions=partitions,
        missing_splits=missing,
        complete=complete,
        all_partitions_sampled=all_sampled,
        all_expectancies_positive=all_positive,
        expectancy_spread=expectancy_spread,
    )


def partition_stability_payload(
    report: PartitionStabilityReport,
) -> dict[str, object]:
    """Return deterministic serializable partition evidence."""

    return {
        "partitions": [
            {
                "split": partition.split.value,
                "sample_size": partition.sample_size,
                "expectancy": partition.expectancy,
                "profit_factor": partition.profit_factor,
                "average_r": partition.average_r,
                "maximum_drawdown": partition.maximum_drawdown,
                "positive_expectancy": partition.positive_expectancy,
            }
            for partition in report.partitions
        ],
        "missing_splits": [split.value for split in report.missing_splits],
        "complete": report.complete,
        "all_partitions_sampled": report.all_partitions_sampled,
        "all_expectancies_positive": report.all_expectancies_positive,
        "expectancy_spread": report.expectancy_spread,
        "calibration_authoritative": report.calibration_authoritative,
    }


def _partition_performance(
    split: HistoricalSignalSplit,
    report: BacktestReport,
) -> PartitionPerformance:
    return PartitionPerformance(
        split=split,
        sample_size=report.total_trades,
        expectancy=report.expectancy,
        profit_factor=report.profit_factor,
        average_r=report.average_risk_reward,
        maximum_drawdown=report.maximum_drawdown,
        positive_expectancy=report.expectancy > 0.0,
    )


__all__ = [
    "PartitionPerformance",
    "PartitionStabilityReport",
    "build_partition_stability_report",
    "partition_stability_payload",
]
