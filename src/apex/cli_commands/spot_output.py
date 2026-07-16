"""Shared output handling for canonical spot CLI commands."""

from __future__ import annotations

import json
from collections.abc import Mapping

import typer

from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.spot import render_spot_analysis, render_spot_plan, render_spot_scan


def output_mode(value: str) -> OutputMode:
    """Validate one CLI output format."""

    try:
        return normalize_output_mode(value)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc


def emit_spot_analysis(
    payload: Mapping[str, object],
    *,
    mode: OutputMode,
    title: str,
) -> None:
    """Emit JSON or trader-facing spot analysis text."""

    if mode is OutputMode.JSON:
        _emit_json(payload)
        return
    typer.echo(render_spot_analysis(payload, mode=mode, title=title))


def emit_spot_plan(payload: Mapping[str, object], *, mode: OutputMode) -> None:
    """Emit JSON or trader-facing standalone spot planning text."""

    if mode is OutputMode.JSON:
        _emit_json(payload)
        return
    typer.echo(render_spot_plan(payload, mode=mode))


def emit_spot_scan(payload: Mapping[str, object], *, mode: OutputMode) -> None:
    """Emit JSON or trader-facing live spot scan text."""

    if mode is OutputMode.JSON:
        _emit_json(payload)
        return
    typer.echo(render_spot_scan(payload, mode=mode))


def _emit_json(payload: Mapping[str, object]) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True))


__all__ = ["emit_spot_analysis", "emit_spot_plan", "emit_spot_scan", "output_mode"]
