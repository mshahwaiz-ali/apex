"""Helpers for controlling the active Typer command surface."""

from __future__ import annotations

from collections.abc import Collection

import typer


def remove_registered_commands(app: typer.Typer, names: Collection[str]) -> None:
    """Remove named commands from a Typer registry while preserving their code."""

    blocked = frozenset(names)
    app.registered_commands[:] = [
        command
        for command in app.registered_commands
        if command.name not in blocked
    ]
