"""Curated user-facing help for the Apex CLI."""

from __future__ import annotations

import typer


_COMMAND_HELP: dict[str, tuple[str, str]] = {
    "version": ("System", "Show the installed Apex version."),
    "validate-config": ("System", "Check configuration files and print the resolved settings."),
    "smoke": ("System", "Run a quick startup check to confirm Apex loads correctly."),
    "fetch": ("Market data", "Download recent public candles for one trading pair."),
    "ticker": ("Market data", "Show the latest public price and ticker data for one trading pair."),
    "analyze": ("Find futures trades", "Analyze one futures pair and print the current trade plan or rejection reason."),
    "scan": ("Find futures trades", "Scan and rank the configured futures market for actionable setups."),
    "simulate-current-setup": ("Find futures trades", "Paper-simulate one currently approved setup without placing an order."),
    "spot-analyze": ("Find spot trades", "Analyze one spot pair and show the selected long-only plan or rejection reason."),
    "spot-orchestrate": ("Find spot trades", "Build a complete spot plan from validated market structure and account limits."),
    "spot-live": ("Find spot trades", "Fetch live market data and run the complete spot analysis workflow."),
    "spot-scan-live": ("Find spot trades", "Scan selected spot pairs and rank the best currently eligible opportunities."),
    "spot-plan": ("Find spot trades", "Build a bounded spot entry, allocation, target, and exit plan."),
    "export-dataset": ("Research and backtesting", "Export candles and analysis data for research."),
    "chronological-backtest": ("Research and backtesting", "Replay historical setups in time order with realistic trading costs."),
    "compare-backtests": ("Research and backtesting", "Compare two saved backtest reports."),
    "chronological-backtest-campaign": ("Research and backtesting", "Run a reproducible historical campaign for one futures risk mode."),
    "historical-futures-edge-report": ("Research and backtesting", "Summarize historical futures performance by data split and setup segment."),
    "historical-futures-edge-validate": ("Research and backtesting", "Check whether historical futures results remain stable on untouched test data."),
    "forward-edge-validate": ("Paper validation", "Evaluate completed paper trades and measure forward performance by setup segment."),
    "evidence-bundle-inspect": ("Paper validation", "Inspect a saved validation evidence bundle before review."),
    "evidence-pipeline-run": ("Paper validation", "Build the complete reproducible validation evidence bundle."),
    "paper-validation-review": ("Paper validation", "Review saved paper evidence against the expected performance model."),
    "paper-validation-generate": ("Paper validation", "Create a review input from saved backtest and paper-trading data."),
    "paper-validation-run": ("Paper validation", "Generate and save one complete daily paper-validation snapshot."),
    "paper-validation-daily": ("Paper validation", "Evaluate and save the current daily paper-validation snapshot."),
    "paper-validation-history-review": ("Paper validation", "Review accumulated daily paper-validation history."),
    "funded-readiness-review": ("Funded readiness", "Check provider rules, account limits, evidence, and safety controls for manual review."),
    "funded-readiness-from-report": ("Funded readiness", "Evaluate funded readiness from a saved canonical report."),
    "funded-readiness-from-history": ("Funded readiness", "Evaluate funded readiness using verified paper-validation history."),
}

_GROUP_HELP: dict[str, tuple[str, str]] = {
    "paper": ("Paper trading", "Record, update, review, and monitor simulated trades."),
    "optimize": ("Research and backtesting", "Calibrate strategy settings using controlled historical experiments."),
    "intelligence": ("Advanced tools", "Optional deterministic market-context tools."),
    "execute": ("Advanced tools", "Testnet-only execution and safety commands. No real-money trading."),
    "dataset": ("Research and backtesting", "Acquire, split, verify, and replay reproducible historical datasets."),
}


def _classify_unknown_command(name: str) -> tuple[str, str] | None:
    """Return a plain-language fallback for dynamically registered commands."""

    if name.startswith("spot-"):
        return "Find spot trades", "Run a spot-market analysis or planning workflow."
    if name.startswith("paper-") or name.startswith("forward-"):
        return "Paper validation", "Run a paper-trading or forward-validation workflow."
    if name.startswith("funded-"):
        return "Funded readiness", "Run a funded-account evidence or readiness check."
    if any(token in name for token in ("backtest", "historical", "evidence")):
        return "Research and backtesting", "Run a reproducible research or evidence workflow."
    return None


def apply_curated_help(app: typer.Typer) -> None:
    """Apply workflow-oriented descriptions without changing command names or behavior."""

    app.info.help = (
        "Find and evaluate crypto trade opportunities with deterministic risk controls. "
        "Start with `apex scan` for futures or `apex spot-scan-live` for spot."
    )
    app.info.epilog = (
        "Quick start:\n"
        "  apex scan --help\n"
        "  apex analyze BTCUSDT --help\n"
        "  apex spot-scan-live --help\n"
        "  apex paper --help\n\n"
        "Apex analyzes and paper-tests trades; it does not authorize real-money execution."
    )

    for command in app.registered_commands:
        name = command.name
        if name is None:
            continue
        curated = _COMMAND_HELP.get(name) or _classify_unknown_command(name)
        if curated is None:
            command.rich_help_panel = "Advanced tools"
            continue
        panel, description = curated
        command.rich_help_panel = panel
        command.help = description

    for group in app.registered_groups:
        name = group.name
        if name is None:
            continue
        curated = _GROUP_HELP.get(name)
        if curated is None:
            group.rich_help_panel = "Advanced tools"
            continue
        panel, description = curated
        group.rich_help_panel = panel
        group.help = description
