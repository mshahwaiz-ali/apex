from datetime import UTC, date, datetime
from pathlib import Path

from apex.validation import ForwardValidationReport, ProductionEligibility
from apex.validation.history import (
    DailyValidationRecord,
    DailyValidationStore,
    strategy_sample_shortfalls,
)


def _record(day: int, closed: int) -> DailyValidationRecord:
    generated_at = datetime(2026, 7, day, 12, tzinfo=UTC)
    return DailyValidationRecord(
        trading_date=date(2026, 7, day),
        generated_at=generated_at,
        report=ForwardValidationReport(
            schema_version=1,
            generated_at=generated_at,
            eligibility=ProductionEligibility.INSUFFICIENT_SAMPLE,
            reasons=(),
            closed_paper_trades=closed,
            modeled_trades=100,
            win_rate_deviation=0.1,
            expectancy_deviation=0.2,
            drawdown_increase=0.1,
        ),
        closed_trades_by_strategy={"breakout_retest": closed},
    )


def test_daily_store_replaces_same_date_and_sorts(tmp_path: Path) -> None:
    store = DailyValidationStore(tmp_path / "daily.json")

    store.upsert(_record(15, 5))
    store.upsert(_record(14, 3))
    records = store.upsert(_record(15, 8))

    assert [item.trading_date.day for item in records] == [14, 15]
    assert records[-1].report.closed_paper_trades == 8
    assert store.load() == records


def test_strategy_sample_shortfalls_are_explicit() -> None:
    assert strategy_sample_shortfalls(
        {"breakout_retest": 7, "trend_pullback": 12},
        minimum_per_strategy=10,
    ) == {"breakout_retest": 3}
