"""Focused navigation for the public Apex CLI."""

from __future__ import annotations

import typer


def install_professional_navigation(app: typer.Typer) -> None:
    """Keep the public command surface flat and trade-discovery focused."""

    app.info.help = (
        "Discover and evaluate Binance USDT perpetual-futures trade opportunities. "
        "Start with `apex scan`."
    )
    app.info.epilog