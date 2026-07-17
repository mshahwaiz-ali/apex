"""Install the focused public Apex CLI commands."""

from __future__ import annotations

import typer

from apex.cli_commands.analysis import register_analysis_commands
from apex.cli_commands.backtesting import register_backtesting_commands
from apex.cli_commands.scanner import register_scanner_commands
from apex.cli_commands.system import register_system_commands
from apex.cli_overlay import remove_commands, remove_groups


def install_cli_commands(app: typer.Typer, paper_app: typer.Typer | None = None) -> None:
    """Expose only the focused trade-discovery command surface."""

    del paper_app
    remove_groups(app, {"paper", "dataset", "execute", "optimize", "intelligence"})
    remove_commands(
        app,
        {
            "version",
            "validate-config",
            "config-check",
            "smoke",
            "fetch",
            "ticker",
            "analyze",
            "scan",
            "backtest",
        },
    )
    register_system_commands(app)
    register_analysis_commands(app)
    register_scanner_commands(app)
    register_backtesting_commands(app)


__all__ = ["install_cli_commands"]
