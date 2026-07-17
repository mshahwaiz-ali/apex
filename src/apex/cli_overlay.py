"""Helpers for replacing selected Typer commands and command groups."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import typer


def command_name(command: Any) -> str:
    """Return the effective Typer command or group name."""

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


def remove_groups(app: typer.Typer, names: Iterable[str]) -> None:
    """Remove named Typer sub-applications from the public command surface."""

    blocked = set(names)
    app.registered_groups[:] = [
        group for group in app.registered_groups if command_name(group) not in blocked
    ]


def register(app: typer.Typer, name: str) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Return a typed decorator for one explicit command name."""

    return app.command(name)


__all__ = ["command_name", "register", "remove_commands", "remove_groups"]
