"""Install the focused public Apex CLI commands."""

from __future__ import annotations

import typer

from apex.cli_commands.analysis import register_analysis_commands
from apex.cli_commands.backtesting import register_backtesting_commands
from apex.cli_commands.scanner import register_scanner_commands
from apex.cli_commands.system import register_system_commands
from apex.cli_overlay import remove_commands, remove_groups

_LEGACY_COMMANDS = {
    "analyze",
    "backtest",
    "chronological-backtest",
    "chronological-backtest-campaign",
    "compare-backtests",
    "config-check",
    "export-dataset",
    "fetch",
    "forward-edge-validate",
    "funded-readiness-from-history",
    "funded-readiness-from-report",
    "funded-readiness-review",
    "historical-futures-edge-report",
    "historical-futures-edge-validate",
    "paper-validation-daily",
    "paper-validation-generate",
    "paper-validation-history-review",
    "paper-validation-review",
    "paper-validation-run",
    "scan",
    "simulate-current-setup",
    "smoke",
    "ticker",
    "validate-config",
    "version",
}


def install_cli_commands(app: typer.Typer, paper_app: typer.Typer | None = None) -> None:
    """Expose only the focused trade-discovery command surface."""

    del paper_app
    remove_groups(
        app,
        {
            "paper",
            "dataset",
            "execute",
            "optimize",
            "intelligence",
            "futures",
            "research",
            "validation",
            "system",
        },
    )
    remove_commands(app, _LEGACY_COMMANDS)
    register_system_commands(app)
    register_analysis_commands(app)
    register_scanner_commands(app)
    register_backtesting_commands(app)


__all__ = ["install_cli_commands"]
