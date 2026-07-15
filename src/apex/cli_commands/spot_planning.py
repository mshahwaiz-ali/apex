"""CLI command for canonical long-only spot planning."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.application.spot_account import DEFAULT_SPOT_CONFIG_PATH
from apex.application.spot_plan_io import (
    build_spot_plan_from_files,
    spot_planning_result_to_payload,
    write_spot_planning_result,
)


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
            typer.Option("--output", dir_okay=False),
        ] = None,
    ) -> None:
        """Build a bounded research-only spot entry, allocation, and exit plan."""

        try:
            result = build_spot_plan_from_files(input_path=input_file, config_path=config)
            payload = spot_planning_result_to_payload(result)
            if output is not None:
                write_spot_planning_result(output, result)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
