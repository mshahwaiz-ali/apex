"""Shared output handling for research CLI commands."""

from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from apex.presentation import OutputMode, normalize_cli_output_mode


def output_mode(value: str) -> OutputMode:
    """Validate one research output format."""

    try:
        return normalize_cli_output_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def emit_payload(
    payload: Mapping[str, object],
    *,
    mode: OutputMode,
    rendered: str,
) -> None:
    """Emit deterministic JSON or a trader-facing research summary."""

    if mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(rendered)


__all__ = ["emit_payload", "output_mode"]
