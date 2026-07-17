"""Focused public system commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from apex import __version__
from apex.config import load_settings
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.system import render_config, render_version


def register_system_commands(app: typer.Typer) -> None:
    """Register the minimal public system command surface."""

    @app.command("config-check")
    def config_check(
        config_dir: Annotated[
            Path,
            typer.Option("--config-dir", exists=True, file_okay=False),
        ] = Path("config"),
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Validate and summarize the resolved Apex configuration."""

        output_mode = _output_mode(output)
        settings = load_settings(config_dir)
        payload = settings.model_dump(mode="json")
        _emit(payload, render_config(payload, mode=output_mode), output_mode)

    @app.command("version")
    def version(
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
    ) -> None:
        """Show the installed Apex version."""

        output_mode = _output_mode(output)
        payload = {"version": __version__}
        _emit(payload, render_version(__version__), output_mode)


def _output_mode(value: str) -> OutputMode:
    try:
        return normalize_cli_output_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(text)


__all__ = ["register_system_commands"]
