"""Canonical symbol wrappers for paper-trading CLI commands."""

from __future__ import annotations

import typer

from apex.application import normalize_market_symbol
from apex.cli import paper_record as legacy_paper_record
from apex.cli import paper_update as legacy_paper_update


def register_paper_trading_commands(app: typer.Typer) -> None:
    """Register corrected paper commands while preserving legacy behavior."""

    @app.command("record")
    def paper_record(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
    ) -> None:
        """Analyze and record a setup using a canonical market symbol."""

        legacy_paper_record(
            symbol=normalize_market_symbol(symbol),
            candle_limit=candle_limit,
        )

    @app.command("update")
    def paper_update(
        symbol: str | None = typer.Argument(None, help="Optional market symbol filter."),
        timeframe: str = typer.Option("5m", "--timeframe"),
        candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
    ) -> None:
        """Update paper trades, optionally filtering by a canonical symbol."""

        canonical = normalize_market_symbol(symbol) if symbol is not None else None
        legacy_paper_update(
            symbol=canonical,
            timeframe=timeframe,
            candle_limit=candle_limit,
        )
