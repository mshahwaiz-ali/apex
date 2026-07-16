"""Professional workflow navigation for the Apex CLI."""

from __future__ import annotations

from copy import copy
from dataclasses import dataclass

import typer


@dataclass(frozen=True)
class CommandRoute:
    group: str
    name: str
    help: str
    example: str | None = None


_ROUTES: dict[str, CommandRoute] = {
    "analyze": CommandRoute(
        "futures",
        "analyze",
        "Analyze one futures market and show the current setup, risk plan