"""Professional workflow navigation for the Apex CLI."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import typer


@dataclass(frozen=True)
class CommandRoute:
    source: str
    group: str
    name: str
    help: str


_ROUTES: tuple[CommandRoute, ...] = (
    CommandRoute(
        "analyze",
        "futures",
        "analyze",
        "Analyze one futures market and show the current setup, entry plan, and risk controls.",
    ),
    CommandRoute(
        "scan",
        "futures",
        "scan",
        "Scan the configured futures universe and rank actionable opportunities.",
    ),
    CommandRoute(
        "simulate-current-setup",
        "futures",
        "simulate",
        "Paper-simulate one currently approved futures setup.",
    ),
    CommandRoute(
        "spot-analyze",
        "spot",
        "analyze",
        "Analyze one spot market and show the selected long-only plan or rejection reason.",
    ),
    CommandRoute(
        "spot-live",
        "spot",
        "live",
        "Fetch live market data and run the complete spot analysis workflow.",
    ),
    CommandRoute(
        "spot-scan-live",
        "spot",
        "scan",
        "Scan selected spot markets and rank the best currently eligible opportunities.",
    ),
    CommandRoute(
        "spot-plan",
        "spot",
        "plan",
        "Build a bounded spot entry, allocation, target, and exit plan.",
    ),
    CommandRoute(
        "spot-orchestrate",
        "spot",
        "orchestrate",
        "Build a complete spot plan from validated structure and account limits.",
    ),
    CommandRoute(
        "chronological-backtest",
        "research",
        "backtest",
        "Replay historical setups in chronological order with modeled costs.",
    ),
    CommandRoute(
        "chronological-backtest-campaign",
        "research",
        "campaign",
        "Run a reproducible historical futures campaign for one risk mode.",
    ),
    CommandRoute(
        "compare-backtests",
        "research",
        "compare",
        "Compare two saved backtest reports.",
    ),
    CommandRoute(
        "historical-futures-edge-report",
        "research",
        "edge-report",
        "Summarize historical futures performance by split and setup segment.",
    ),
    CommandRoute(
        "historical-futures-edge-validate",
        "research",
        "edge-validate",
        "Check historical performance stability on untouched test data.",
    ),
    CommandRoute(
        "export-dataset",
        "research",
        "export",
        "Export candles and analysis data for reproducible research.",
    ),
    CommandRoute(
        "forward-edge-validate",
        "validation",
        "forward-edge",
        "Evaluate completed paper trades and measure forward performance.",
    ),
    CommandRoute(
        "evidence-bundle-inspect",
        "validation",
        "inspect-evidence",
        "Inspect a saved validation evidence bundle.",
    ),
    CommandRoute(
        "evidence-pipeline-run",
        "validation",
        "build-evidence",
        "Build the complete reproducible validation evidence bundle.",
    ),
    CommandRoute(
        "paper-validation-review",
        "validation",
        "review",
        "Review saved paper evidence against the expected performance model.",
    ),
    CommandRoute(
        "paper-validation-run",
        "validation",
        "daily",
        "Generate and save one complete daily paper-validation snapshot.",
    ),
    CommandRoute(
        "paper-validation-history-review",
        "validation",
        "history",
        "Review accumulated daily paper-validation history.",
    ),
    CommandRoute(
        "funded-readiness-review",
        "validation",
        "funded-readiness",
        "Check provider rules, evidence, account limits, and safety controls.",
    ),
    CommandRoute(
        "validate-config",
        "system",
        "config",
        "Validate Apex configuration and print the resolved settings.",
    ),
    CommandRoute(
        "smoke",
        "system",
        "check",
        "Run a quick startup check to confirm Apex loads correctly.",
    ),
    CommandRoute(
        "fetch",
        "system",
        "candles",
        "Download recent public candles for one market.",
    ),
    CommandRoute(
        "ticker",
        "system",
        "ticker",
        "Show the latest public ticker data for one market.",
    ),
    CommandRoute(
        "version",
        "system",
        "version",
        "Show the installed Apex version.",
    ),
)

_GROUPS: dict[str, tuple[str, str]] = {
    "futures": (
        "Futures trade discovery",
        "Find and evaluate leveraged futures opportunities. No orders are placed.",
    ),
    "spot": (
        "Spot trade discovery",
        "Find and evaluate long-only cash-spot opportunities.",
    ),
    "research": (
        "Research and backtesting",
        "Run reproducible datasets, backtests, comparisons, and calibration workflows.",
    ),
    "validation": (
        "Validation and readiness",
        "Review paper evidence, historical stability, and manual readiness gates.",
    ),
    "system": (
        "System and market data",
        "Check configuration, connectivity, version, and raw public market data.",
    ),
}


def _command_by_name(app: typer.Typer, name: str) -> Any | None:
    for command in app.registered_commands:
        if command.name == name:
            return command
    return None


def _hide_legacy_command(command: Any) -> None:
    command.hidden = True


def _hide_legacy_group(app: typer.Typer, name: str) -> None:
    for group in app.registered_groups:
        if group.name == name:
            group.hidden = True
            return


def install_professional_navigation(app: typer.Typer) -> None:
    """Expose workflow groups while preserving hidden legacy command aliases."""

    group_apps: dict[str, typer.Typer] = {}
    for group_name, (title, description) in _GROUPS.items():
        group_app = typer.Typer(
            name=group_name,
            help=description,
            no_args_is_help=True,
            rich_markup_mode="rich",
        )
        group_app.info.epilog = f"{title}. Use `apex {group_name} COMMAND --help` for details."
        group_apps[group_name] = group_app
        app.add_typer(group_app, name=group_name, rich_help_panel="Workflows")

    for route in _ROUTES:
        source = _command_by_name(app, route.source)
        if source is None or source.callback is None:
            continue
        group_apps[route.group].command(
            route.name,
            help=route.help,
            no_args_is_help=source.no_args_is_help,
            context_settings=source.context_settings,
        )(source.callback)
        _hide_legacy_command(source)

    for legacy_group in ("optimize", "intelligence", "dataset"):
        _hide_legacy_group(app, legacy_group)

    app.info.help = (
        "Professional crypto trade discovery, paper validation, and research workflows. "
        "Start with `apex futures scan` or `apex spot scan`."
    )
    app.info.epilog = (
        "Quick start:\n"
        "  apex futures scan --help\n"
        "  apex futures analyze BTCUSDT --help\n"
        "  apex spot scan --help\n"
        "  apex paper --help\n"
        "  apex research --help\n\n"
        "Apex does not authorize real-money execution."
    )
