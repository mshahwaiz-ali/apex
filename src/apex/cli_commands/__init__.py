"""Install corrected CLI commands."""

from __future__ import annotations

import typer

from apex.cli_commands.analysis import register_analysis_commands
from apex.cli_commands.backtesting import register_backtesting_commands
from apex.cli_commands.market_data import register_market_data_commands
from apex.cli_overlay import remove_commands


def install_cli_commands(app: typer.Typer) -> None:
    remove_commands(app, {"fetch", "ticker", "analyze", "backtest"})
    register_market_data_commands(app)
    register_analysis_commands(app)
    register_backtesting_commands(app)
