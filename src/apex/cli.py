"""Focused Apex command-line root."""

from __future__ import annotations

import typer

app = typer.Typer(
    help="Discover and evaluate Binance USDT perpetual-futures trade opportunities.",
    no_args_is_help=True,
)


if __name__ == "__main__":
    app()
