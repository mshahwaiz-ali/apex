"""Idempotent scheduled daily reporting for paper validation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from apex.paper_trading.forward_validation import (
    ForwardPaperDailyReport,
    build_forward_paper_daily_report,
    load_and_verify_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.paper_trading.store import PaperTradeStore


@dataclass(frozen=True, slots=True)
class ScheduledDailyReportResult:
    """Outcome of one unattended daily-report invocation."""

    report_date: date
    path: str
    created: bool
    report: ForwardPaperDailyReport


def previous_utc_date(now: datetime) -> date:
    """Return the fully completed UTC calendar day preceding ``now``."""

    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("daily report reference time must be timezone-aware")
    return (now.astimezone(timezone.utc) - timedelta(days=1)).date()


def run_scheduled_daily_report(
    *,
    store: PaperTradeStore,
    output_directory: Path,
    generated_at: datetime,
    report_date: date | None = None,
) -> ScheduledDailyReportResult:
    """Create or verify one immutable daily report without silent overwrite."""

    if generated_at.tzinfo is None or generated_at.utcoffset() is None:
        raise ValueError("daily report generation time must be timezone-aware")

    resolved_date = report_date or previous_utc_date(generated_at)
    output_path = output_directory / f"{resolved_date.isoformat()}.json"
    if output_path.exists():
        existing = load_and_verify_forward_paper_daily_report(output_path)
        existing_date = existing.payload.get("report_date")
        if existing_date != resolved_date.isoformat():
            raise ValueError("existing daily report date does not match its filename")
        return ScheduledDailyReportResult(
            report_date=resolved_date,
            path=str(output_path),
            created=False,
            report=existing,
        )

    report = build_forward_paper_daily_report(
        report_date=resolved_date,
        trades=store.load(),
        generated_at=generated_at,
    )
    write_forward_paper_daily_report(report, output_path)
    verified = load_and_verify_forward_paper_daily_report(output_path)
    return ScheduledDailyReportResult(
        report_date=resolved_date,
        path=str(output_path),
        created=True,
        report=verified,
    )
