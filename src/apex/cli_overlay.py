"""Helpers for replacing selected Typer commands without rewriting the legacy CLI."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import typer


def command_name(command: Any) -> str:
    """Return the effective Typer command name for a registered callback."""

    explicit = getattr(command, "name", None)
    if explicit:
        return str(explicit)
    callback = getattr(command, "callback", None)
    callback_name = getattr(callback, "__name__", "")
    return callback_name.replace("_", "-")


def remove_commands(app: typer.Typer, names: Iterable[str]) -> None:
    """Remove named commands before registering corrected replacements."""

    blocked = set(names)
    app.registered_commands[:] = [
        command for command in app.registered_commands if command_name(command) not in blocked
    ]


def register(app: typer.Typer, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a typed decorator for one explicit command name."""

    return app.command(name)
