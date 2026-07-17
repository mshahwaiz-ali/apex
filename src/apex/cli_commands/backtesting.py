"""Focused public backtest command."""

from __future__ import annotations

import typer

from apex.cli import backtest as legacy_backtest


def register_backtesting_commands(app: typer.Typer) -> None:
    """Register one focused strategy-evaluation command."""

    @app.command("backtest")
    def backtest(
        symbol: str = typer.Argument(..., help="Trading pair, for example BTCUSDT."),
       