"""CLI command for canonical research-only spot analysis."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex.application.spot_analysis import spot_analysis_result_to_payload
from apex.application.spot_analysis_io import (
    DEFAULT_SPOT_CONFIG_PATH,
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
    analyze_spot_from_files,
    write_spot_analysis_result,
)


def register_spot_analysis_commands(app: typer.Typer) -> None:
    """Register the canonical spot analysis command."""

    @app.command("spot-analyze")
    def spot_analyze(
        input_file: Annotated[
            Path,
            typer.Option("--input", exists=True, dir_okay=False, readable=True),
        ],
        config: Annotated[
            Path,
            typer.Option("--config", exists=True, dir_okay=False, readable=True),
        ] = DEFAULT_SPOT_CONFIG_PATH,
        strategy_config: Annotated[
            Path,
            typer.Option(
                "--strategy-config",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ] = DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
        output: Annotated[
            Path | None,
            typer.Option("--output", dir_okay=False),
        ] = None,
    ) -> None:
        """Evaluate canonical spot strategies and build a bounded plan when approved."""

        try:
            result = analyze_spot_from_files(
                input_path=input_file,
                product_config_path=config,
                strategy_config_path=strategy_config,
            )
            payload = spot_analysis_result_to_payload(result)
            if output is not None:
                write_spot_analysis_result(output, result)
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc

        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
