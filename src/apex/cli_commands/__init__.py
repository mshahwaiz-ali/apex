"""Register the public Apex CLI commands."""

from __future__ import annotations

import typer

from apex.cli_commands.analysis import register_analysis_commands
from apex.cli_commands.backtesting import register_backtesting_commands
from apex.cli_commands.research import register_research_commands
from apex.cli_commands.scanner import register_scanner_commands
from apex.cli_commands.system import register_system_commands


def install_cli_commands(app: typer.Typer) -> None:
    """Register the focused command surface."""

    register_system_commands(app)
    register_analysis_commands(app)
    register_scanner_commands(app)
    register_backtesting_commands(app)
    register_research_commands(app)


__all__ = ["install_cli_commands"]
