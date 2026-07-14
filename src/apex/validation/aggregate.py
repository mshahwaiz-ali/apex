"""Aggregate forward-paper validation history review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.validation.forward import ProductionEligibility
from apex.validation.history import DailyValidationRecord


class AggregateHistoryReason(StrEnum):
    """Stable machine-readable aggregate P1 blocker codes."""

    INSUFFICIENT_VALIDATION_DAYS = "INSUFFICIENT_VALIDATION_DAYS"
    INSUFFICIENT_TOTAL_SAMPLES = "INSUFFICIENT_TOTAL_SAMPLES"
    INSUFFICIENT_STRATEGY_SAMPLES = "INSUFFICIENT_STRATEGY_SAMPLES"
    INSUFFICIENT_FAILURE_FREE_STREAK = "INSUFFICIENT_FAILURE_FREE_STREAK"
    INCONSISTENT_DAILY_ELIGIBILITY = "INCONSISTENT_DAILY_ELIGIBILITY"
    WIN_RATE_DETERIORATION = "WIN_RATE_DETERIORATION"
    EXPECTANCY_DETERIORATION = "EXPECTANCY_DETERIORATION"
    DRAWDOWN_DETERIORATION = "DRAWDOWN_DETERIORATION"


@dataclass(frozen=True, slots=True)
class AggregateHistoryThresholds:
    """Operator-controlled thresholds for aggregate P1 history review."""

    minimum_validation_days: int = 10
    minimum_total_samples: int = 30
    minimum_samples_per_strategy: int = 10
    minimum_consecutive_failure_free_days: int = 5
    minimum_ready_day_ratio: float = 0.80
    maximum_win_rate_deterioration: float = 0.05
    maximum_expectancy_deterioration: float = 0.10
    maximum_drawdown_deterioration: float = 0.05

    def __post_init__(self) -> None:
        if (
            min(
                self.minimum_validation_days,
                self.minimum_total_samples,
                self.minimum_samples_per_strategy,
                self.minimum_consecutive_failure_free_days,
            )
            < 1
        ):
            raise ValueError("aggregate history count thresholds must be positive")
        if not 0.0 <= self.minimum_ready_day_ratio <= 1.0:
            raise ValueError("minimum ready-day ratio must be between zero and one")
        for name in (
            "maximum_win_rate_deterioration",
            "maximum_expectancy_deterioration",
            "maximum_drawdown_deterioration",
        ):
            if getattr(self, name) < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} cannot be negative")


@dataclass(frozen=True, slots=True)
class AggregateHistoryReport:
    """Schema-versioned aggregate P1 history decision consumed by R1."""

    schema_version: int
    generated_at: datetime
    ready_for_funded_review: bool
    reasons: tuple[AggregateHistoryReason, ...]
    validation_days: int
    total_samples: int
    samples_by_strategy: dict[str, int]
    strategy_sample_shortfalls: dict[str, int]
    consecutive_failure_free_days: int
    mature_validation_days: int
    ready_validation_days: int
    ready_day_ratio: float
    win_rate_deterioration: float
    expectancy_deterioration: float
    drawdown_deterioration: float

    def __post_init__(self) -> None:
        if self.schema_version != 1:
            raise ValueError("unsupported aggregate-history schema version")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("aggregate-history report time must be timezone-aware")
        if self.ready_for_funded_review and self.reasons:
            raise ValueError("ready aggregate-history report cannot contain blockers")


def evaluate_aggregate_history(
    records: tuple[DailyValidationRecord, ...],
    *,
    thresholds: AggregateHistoryThresholds,
    generated_at: datetime,
) -> AggregateHistoryReport:
    """Evaluate cumulative daily P1 evidence without double-counting cumulative samples."""

    ordered = tuple(sorted(records, key=lambda item: item.trading_date))
    latest = ordered[-1] if ordered else None
    total_samples = latest.report.closed_paper_trades if latest is not None else 0
    samples_by_strategy = dict(latest.closed_trades_by_strategy) if latest is not None else {}
    shortfalls = {
        strategy: thresholds.minimum_samples_per_strategy - count
        for strategy, count in sorted(samples_by_strategy.items())
        if count < thresholds.minimum_samples_per_strategy
    }

    failure_free_streak = 0
    for record in reversed(ordered):
        if record.report.eligibility is ProductionEligibility.REJECTED:
            break
        failure_free_streak += 1

    mature = tuple(
        record
        for record in ordered
        if record.report.closed_paper_trades >= thresholds.minimum_total_samples
    )
    ready_days = sum(
        record.report.eligibility is ProductionEligibility.READY_FOR_FUNDED_REVIEW
        for record in mature
    )
    ready_ratio = ready_days / len(mature) if mature else 0.0

    win_rate_deterioration = _deterioration(ordered, "win_rate_deviation")
    expectancy_deterioration = _deterioration(ordered, "expectancy_deviation")
    drawdown_deterioration = _deterioration(ordered, "drawdown_increase")

    reasons: list[AggregateHistoryReason] = []
    if len(ordered) < thresholds.minimum_validation_days:
        reasons.append(AggregateHistoryReason.INSUFFICIENT_VALIDATION_DAYS)
    if total_samples < thresholds.minimum_total_samples:
        reasons.append(AggregateHistoryReason.INSUFFICIENT_TOTAL_SAMPLES)
    if not samples_by_strategy or shortfalls:
        reasons.append(AggregateHistoryReason.INSUFFICIENT_STRATEGY_SAMPLES)
    if failure_free_streak < thresholds.minimum_consecutive_failure_free_days:
        reasons.append(AggregateHistoryReason.INSUFFICIENT_FAILURE_FREE_STREAK)
    if (
        not mature
        or latest is None
        or latest.report.eligibility is not ProductionEligibility.READY_FOR_FUNDED_REVIEW
        or ready_ratio < thresholds.minimum_ready_day_ratio
    ):
        reasons.append(AggregateHistoryReason.INCONSISTENT_DAILY_ELIGIBILITY)
    if win_rate_deterioration > thresholds.maximum_win_rate_deterioration:
        reasons.append(AggregateHistoryReason.WIN_RATE_DETERIORATION)
    if expectancy_deterioration > thresholds.maximum_expectancy_deterioration:
        reasons.append(AggregateHistoryReason.EXPECTANCY_DETERIORATION)
    if drawdown_deterioration > thresholds.maximum_drawdown_deterioration:
        reasons.append(AggregateHistoryReason.DRAWDOWN_DETERIORATION)

    unique_reasons = tuple(dict.fromkeys(reasons))
    return AggregateHistoryReport(
        schema_version=1,
        generated_at=generated_at,
        ready_for_funded_review=not unique_reasons,
        reasons=unique_reasons,
        validation_days=len(ordered),
        total_samples=total_samples,
        samples_by_strategy=dict(sorted(samples_by_strategy.items())),
        strategy_sample_shortfalls=shortfalls,
        consecutive_failure_free_days=failure_free_streak,
        mature_validation_days=len(mature),
        ready_validation_days=ready_days,
        ready_day_ratio=ready_ratio,
        win_rate_deterioration=win_rate_deterioration,
        expectancy_deterioration=expectancy_deterioration,
        drawdown_deterioration=drawdown_deterioration,
    )


def _deterioration(records: tuple[DailyValidationRecord, ...], field: str) -> float:
    if len(records) < 2:
        return 0.0
    first = float(getattr(records[0].report, field))
    latest = float(getattr(records[-1].report, field))
    return max(0.0, latest - first)


__all__ = [
    "AggregateHistoryReason",
    "AggregateHistoryReport",
    "AggregateHistoryThresholds",
    "evaluate_aggregate_history",
]
