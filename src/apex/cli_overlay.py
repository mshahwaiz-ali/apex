"""Helpers for replacing selected Typer commands and command groups."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import typer


def command_name(command: Any) -> str:
    """Return the effective Typer command or group name."""

    explicit = getattr(command, "name", None)
    if explicit:
        return