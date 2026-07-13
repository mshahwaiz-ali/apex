"""Normalized market-data CLI commands."""

from __future__ import annotations

import typer

from apex.application import normalize_market_symbol
from apex.cli import fetch_candles as legacy_fetch_candles
from apex.cli import ticker as legacy_ticker


def register_market_data_commands(app: typer.Typer) -> None:
    @app.command("fetch")
    def fetch_candles(
        symbol: str = typer.Argument(..., help="Trading pair, including compact BTCUSDT form."),
        timeframe: str = typer.Option("15m", "--timeframe", "-t"),
        limit: int = typer.Option(10, "--limit", "-l", min=1, max=1000),
    ) -> None:
        legacy_fetch_candles(normalize_market_symbol(symbol), timeframe, limit)

    @app.command("ticker")
    def ticker(
        symbol: str = typer.Argument(..., help="Trading pair, including compact BTCUSDT form."),
    ) -> None:
        legacy_ticker(normalize_market_symbol(symbol))
