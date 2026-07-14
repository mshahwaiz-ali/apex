from datetime import UTC, date, datetime

from apex.validation import (
    AggregateHistoryReason,
    AggregateHistoryThresholds,
    ForwardValidationReport,
    ProductionEligibility,
    evaluate_aggregate_history,
)
from apex.validation.history import DailyValidationRecord


def _record(
    day: int,
    *,
    eligibility: ProductionEligibility = ProductionEligibility.READY_FOR_FUNDED_REVIEW,
    closed: int = 40,
    win_rate_deviation: float = 0.05,
    expectancy_deviation: float = 0.10,
    drawdown_increase: float = 0.05,
) -> DailyValidationRecord:
    generated_at = datetime(2026, 7, day, 12, tzinfo=UTC)
    return DailyValidationRecord(
        trading_date=date(2026, 7, day),
        generated_at=generated_at,
        report=ForwardValidationReport(
            schema_version=1,
            generated_at=generated_at,
            eligibility=eligibility,
            reasons=(),
            closed_paper_trades=closed,
            modeled_trades=100,
            win_rate_deviation=win_rate_deviation,
            expectancy_deviation=expectancy_deviation,
            drawdown_increase=drawdown_increase,
        ),
        closed_trades_by_strategy={"breakout_retest": 20, "trend_pullback": 20},
    )


def test_aggregate_history_becomes_ready_from_consistent_cumulative_evidence() -> None:
    report = evaluate_aggregate_history(
        tuple(_record(day) for day in range(1, 11)),
        thresholds=AggregateHistoryThresholds(),
        generated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    assert report.ready_for_funded_review is True
    assert report.reasons == ()
    assert report.total_samples == 40
    assert report.validation_days == 10
    assert report.consecutive_failure_free_days == 10


def test_aggregate_history_reports_deterioration_and_failed_streak() -> None:
    records = (
        *(_record(day) for day in range(1, 9)),
        _record(9, eligibility=ProductionEligibility.REJECTED),
        _record(
            10,
            win_rate_deviation=0.20,
            expectancy_deviation=0.30,
            drawdown_increase=0.20,
        ),
    )

    report = evaluate_aggregate_history(
        records,
        thresholds=AggregateHistoryThresholds(),
        generated_at=datetime(2026, 7, 11, tzinfo=UTC),
    )

    assert report.ready_for_funded_review is False
    assert AggregateHistoryReason.INSUFFICIENT_FAILURE_FREE_STREAK in report.reasons
    assert AggregateHistoryReason.WIN_RATE_DETERIORATION in report.reasons
    assert AggregateHistoryReason.EXPECTANCY_DETERIORATION in report.reasons
    assert AggregateHistoryReason.DRAWDOWN_DETERIORATION in report.reasons
