"""Unattended daily-report command for P1 paper validation."""

from __future__ import annotations

from datetime import UTC, date, datetime

import typer

from apex.application import bootstrap
from apex.paper_trading.daily_operations import run_scheduled_daily_report
from apex.paper_trading.store import PaperTradeStore


def register_paper_daily_command(app: typer.Typer) -> None:
    """Register the idempotent daily paper-report command."""

    @app.command("scheduled-daily-report")
    def scheduled_daily_report(
        report_date: str | None = typer.Option(
            None,
            "--report-date",
            help="Optional UTC date in YYYY-MM-DD; defaults to the previous UTC day.",
        ),
    ) -> None:
        """Create or verify one immutable daily paper-validation report."""

        try:
            context = bootstrap()
            generated_at = datetime.now(UTC)
            resolved_date = date.fromisoformat(report_date) if report_date is not None else None
            base = context.settings.data_dir / "paper_trading"
            result = run_scheduled_daily_report(
                store=PaperTradeStore(base / "trades.json"),
                output_directory=base / "daily",
                generated_at=generated_at,
                report_date=resolved_date,
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "PAPER_DAILY_REPORT "
            f"| date={result.report_date.isoformat()} "
            f"| created={str(result.created).lower()} "
            f"| report_sha256={result.report.report_sha256} "
            f"| output={result.path}"
        )
