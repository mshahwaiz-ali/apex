"""CLI integration for setup-specific futures historical-edge reports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting import (
    build_historical_futures_edge_report,
    load_historical_edge_report,
    write_historical_edge_report,
    write_historical_edge_report_sqlite,
)


def register_historical_futures_edge_commands(app: typer.Typer) -> None:
    """Register verified campaign-to-edge reporting commands."""

    @app.command("historical-futures-edge-report")
    def historical_futures_edge_report(
        result_file: Annotated[
            Path,
            typer.Option("--result", exists=True, dir_okay=False, readable=True),
        ],
        execution_manifest: Annotated[
            Path,
            typer.Option(
                "--execution-manifest",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ],
        output_file: Annotated[
            Path,
            typer.Option("--output", dir_okay=False),
        ],
        sqlite_file: Annotated[
            Path | None,
            typer.Option("--sqlite", dir_okay=False),
        ] = None,
        force: Annotated[
            bool,
            typer.Option("--force", help="Allow replacing an existing JSON report."),
        ] = False,
    ) -> None:
        """Create split-isolated edge profiles from a completed N4.7 campaign."""

        try:
            report = build_historical_futures_edge_report(
                result_path=result_file,
                execution_manifest_path=execution_manifest,
                generated_at=datetime.now(UTC),
            )
            write_historical_edge_report(output_file, report, force=force)
            verified = load_historical_edge_report(output_file)
            if verified != report:
                raise ValueError("historical futures edge report changed after reload")
            if sqlite_file is not None:
                write_historical_edge_report_sqlite(sqlite_file, report)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(
            "HISTORICAL_FUTURES_EDGE_REPORT_COMPLETED "
            f"| campaign_id={report['campaign_id']} "
            f"| trades={report['trade_count']} "
            f"| profiles={report['profile_count']} "
            f"| report_id={report['report_id']} "
            f"| output={output_file}"
        )
