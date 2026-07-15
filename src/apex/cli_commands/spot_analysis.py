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
