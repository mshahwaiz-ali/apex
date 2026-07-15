from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from apex.paper_trading.daily_operations import previous_utc_date, run_scheduled_daily_report
from apex.paper_trading.store import PaperTradeStore


def test_previous_utc_date_uses_completed_day() -> None:
    now = datetime(2026, 7, 16, 0, 5, tzinfo=timezone.utc)

    assert previous_utc_date(now) == date(2026, 7, 15)


def test_scheduled_daily_report_is_idempotent(tmp_path: Path) -> None:
    store = PaperTradeStore(tmp_path / "trades.json")
    output_directory = tmp_path / "daily"
    now = datetime(2026, 7, 16, 0, 5, tzinfo=timezone.utc)

    first = run_scheduled_daily_report(
        store=store,
        output_directory=output_directory,
        generated_at=now,
    )
    second = run_scheduled_daily_report(
        store=store,
        output_directory=output_directory,
        generated_at=now,
    )

    assert first.created is True
    assert second.created is False
    assert first.report_date == date(2026, 7, 15)
    assert first.report.report_sha256 == second.report.report_sha256
    assert Path(first.path).is_file()
