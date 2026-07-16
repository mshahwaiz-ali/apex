"""Curated user-facing help for the Apex CLI."""

from __future__ import annotations

import typer


_COMMAND_HELP: dict[str, tuple[str, str]] = {
    "version": ("System", "Show the installed Apex version."),
    "validate-config": ("System", "Check all Apex configuration files and print the resolved settings."),
    "smoke": ("System", "Run a quick startup check to confirm Apex can load correctly."),
    "fetch": ("Market data", "Download recent public candles for one trading pair."