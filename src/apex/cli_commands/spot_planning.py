"""CLI command for canonical long-only spot planning."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from apex.application.spot_account import DEFAULT_SPOT_CONFIG_PATH
from apex.application.spot_plan_io import (
    build_spot_plan_from_files,
    spot_planning_result_to_payload,
    write_spot_planning_result,
)
from apex.cli_commands.spot_output import emit_spot_plan, output_mode


def register_spot_planning_commands(app: typer.Typer) -> None:
    """Register the canonical spot planning command."""

    @app.command("spot-plan")
    def spot_plan(
        input_file: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        config: Annotated[
            Path,
            typer.Option("--config", exists=True, dir_okay=False, readable=True),
        ] = DEFAULT_SPOT_CONFIG_PATH,
        output: Annotated[
            Path | None,
            typer.Option("--output", dir_okay=False, help="Optional JSON file destination."),
        ] = None,
        output_format: Annotated[
            str,
            typer.Option("--format", help="text or json"),
        ] = "text",
    ) -> None:
        """Build a bounded research-only spot entry, allocation, and exit plan."""

        mode = output_mode(output_format)
        try:
            result = build_spot_plan_from_files(input_path=input_file, config_path=config)
            payload = spot_planning_result_to_payload(result)
            if output is not None:
                write_spot_planning_result(output, result)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        emit_spot_plan(payload, mode=mode)
