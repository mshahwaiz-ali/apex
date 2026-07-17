"""Focused public backtest command."""

from __future__ import annotations

import typer

from apex.cli import backtest as legacy_backtest


def register_backtesting_commands(app: typer.Typer) -> None:
    """Register one focused strategy-evaluation command."""

    @app.command("backtest")
    def backtest(
        symbol: str = typer.Argument(..., help="Trading pair, for example BTCUSDT."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(240, "--candles", min=80, max=1000),
        replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
    ) -> None:
        """Evaluate the current discovery setup against subsequent market candles."""

        legacy_backtest(
            symbol=symbol,
            output=output,
            candle_limit=candle_limit,
            replay_timeframe=replay_timeframe,
        )


__all__ = ["register_backtesting_commands"]
