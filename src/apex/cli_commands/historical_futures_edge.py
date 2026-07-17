"""CLI integration for setup-specific futures historical-edge reports."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.backtesting.historical_edge_io import (
    load_historical_edge_report,
    write_historical_edge_report,
    write_historical_edge_report_sqlite,
)
from apex.backtesting.historical_futures_edge import build_historical_futures_edge_report
from apex.cli_commands.research_output import emit_payload, output_mode
from apex.presentation.research import render_edge_report


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
        output_format: Annotated[
            str,
            typer.Option("--format", help="text or json"),
        ] = "text",
    ) -> None:
        """Create split-isolated edge profiles from a completed historical campaign."""

        mode = output_mode(output_format)
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

        emit_payload(
            report,
            mode=mode,
            rendered=render_edge_report(report, output_path=output_file, mode=mode),
        )
