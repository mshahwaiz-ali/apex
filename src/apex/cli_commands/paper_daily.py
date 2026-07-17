"""Unattended daily-report command for paper validation."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import typer

from apex.application import bootstrap
from apex.paper_trading.daily_operations import run_scheduled_daily_report
from apex.paper_trading.store import PaperTradeStore
from apex.presentation import (
    OutputMode,
    normalize_cli_output_mode,
    render_fields,
    render_section,
    render_title,
)


def register_paper_daily_command(app: typer.Typer) -> None:
    """Register the idempotent daily paper-report command."""

    @app.command("scheduled-daily-report")
    def scheduled_daily_report(
        report_date: str | None = typer.Option(
            None,
            "--report-date",
            help="Optional UTC date in YYYY-MM-DD; defaults to the previous UTC day.",
        ),
        format_: str = typer.Option(
            "text",
            "--format",
            help="Presentation format: text or json.",
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
            output_mode = normalize_cli_output_mode(format_)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        payload = {
            "report_date": result.report_date.isoformat(),
            "created": result.created,
            "report_sha256": result.report.report_sha256,
            "output_path": str(result.path),
        }
        if output_mode is OutputMode.JSON:
            typer.echo(json.dumps(payload, indent=2, sort_keys=True))
            return

        sections = [
            render_title("Daily Paper Trading Summary"),
            render_section(
                "Report",
                render_fields(
                    (
                        ("Date", payload["report_date"]),
                        ("New report created", "Yes" if result.created else "No; existing report verified"),
                        ("Evidence checksum", payload["report_sha256"]),
                    )
                ),
            ),
            render_section(
                "Next action",
                "Review the immutable daily evidence and investigate any missing or incomplete activity.",
            ),
        ]
        sections.append(
            render_section("Persistence", render_fields((("Report path", payload["output_path"]),)))
        )
        typer.echo("\n\n".join(sections))
