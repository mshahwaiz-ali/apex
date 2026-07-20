"""Curated user-facing help for the focused Apex CLI."""

from __future__ import annotations

import typer

_COMMAND_HELP: dict[str, tuple[str, str]] = {
    "scan": (
        "Trading",
        "Discover, analyze, and rank Binance USDT perpetual-futures opportunities.",
    ),
    "analyze": (
        "Trading",
        "Analyze one futures symbol and show its entry geometry, targets, and cautions.",
    ),
    "backtest": (
        "Evaluation",
        "Replay historical decisions for one futures symbol.",
    ),
    "config-check": (
        "System",
        "Validate configuration files and print the resolved settings.",
    ),
    "version": ("System", "Show the installed Apex version."),
}


def apply_curated_help(app: typer.Typer) -> None:
    """Apply concise descriptions to the intentionally small command surface."""

    app.info.help = (
        "Apex discovers, analyzes, and evaluates Binance USDT perpetual-futures "
        "opportunities. Start with `apex scan`."
    )
    for command in app.registered_commands:
        name = command.name
        if name is None:
            continue
        curated = _COMMAND_HELP.get(name)
        if curated is None:
            command.hidden = True
            continue
        panel, description = curated
        command.rich_help_panel = panel
        command.help = description


__all__ = ["apply_curated_help"]
