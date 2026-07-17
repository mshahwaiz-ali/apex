"""Curated user-facing help for the focused Apex CLI."""

from __future__ import annotations

import typer


_COMMAND_HELP: dict[str, tuple[str, str]] = {
    "scan": (
        "Trade discovery",
        "Discover, analyze, and rank Binance USDT perpetual-futures opportunities.",
    ),
    "analyze": (
        "Trade discovery",
        "Analyze one futures symbol and show its entry geometry, targets, and cautions.",
    ),
    "backtest": (
        "Evaluation",
        "Replay focused trade-discovery analysis against historical market data.",
    ),
    "config-check": (
        "System",
        "Validate configuration files and print the resolved settings.",