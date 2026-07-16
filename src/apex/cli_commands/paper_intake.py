"""Scheduler-friendly automatic futures and spot paper opportunity intake."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    bootstrap,
    build_futures_account_input,
    build_futures_plan_result,
    create_market_data_services,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
)
from apex.application.paper_intake import (
    intake_futures_scan,
    intake_spot_scan,
    run_locked_paper_intake,
)
from apex.application.spot_live import load_spot_live_account
from apex.application.spot_live_scanner import scan_live_spot
from apex.application.spot_orchestration_io import (
    DEFAULT_SPOT_CONFIG_PATH,
    DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
)
from apex.config.spot import load_spot_product_config
from apex.config.spot_strategies import load_spot_strategy_config
from apex.domain import RiskMode
from apex.domain.spot_market import SpotScannerMode
from apex.paper_trading.intake import IntakeMarketType, IntakeSummary, intake_summary_payload
from apex.paper_trading.store import PaperTradeStore


def register_paper_intake_commands(app: typer.Typer) -> None:
    """Register automatic paper opportunity intake commands."""

    @app.command("intake-futures")
    def intake_futures(
        symbols_file: Path = typer.Option(Path("config/symbols.yaml"), "--symbols-file"),
        mode: str = typer.Option("normal", "--mode", help="normal, gainers, or all"),
        risk_mode: RiskMode = typer.Option(RiskMode.STANDARD, "--risk-mode"),
        wallet_balance: float = typer.Option(100.0, "--wallet-balance", min=0.01),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Scan futures and admit approved actionable plans to the paper store."""

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            symbols = load_symbols(symbols_file)
            risk_config = load_default_risk_config()
            account = build_futures_account_input(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
            )
            with create_market_data_services(context.settings) as services:
                scan = scan_symbols(
                    symbols,
                    services.candles,
                    timeframes=context.settings.analysis_timeframes,
                    timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                    timeframe_max_staleness_seconds=getattr(
                        context.settings,
                        "timeframe_max_staleness_seconds",
                        None,
                    ),
                    candle_limit=candle_limit,
                    risk_config=risk_config,
                    scanner_mode=mode,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    gainer_state_thresholds=getattr(
                        context.settings,
                        "gainer_state_thresholds",
                        None,
                    ),
                )
            store = _paper_store(context.settings.data_dir)
            summary = run_locked_paper_intake(
                market_type=IntakeMarketType.FUTURES,
                data_dir=context.settings.data_dir,
                started_at=started_at,
                run=lambda: intake_futures_scan(
                    scan=scan,
                    store=store,
                    plan_builder=lambda analysis: (
                        build_futures_plan_result(analysis.assessment.setup, account)
                        if analysis.assessment.setup is not None
                        else None
                    ),
                ),
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_summary(summary, output)

    @app.command("intake-spot")
    def intake_spot(
        symbols: Annotated[
            str,
            typer.Option("--symbols", help="Comma-separated cash-spot symbols."),
        ],
        account: Annotated[
            Path,
            typer.Option("--account", exists=True, dir_okay=False, readable=True),
        ],
        config: Annotated[
            Path,
            typer.Option("--config", exists=True, dir_okay=False, readable=True),
        ] = DEFAULT_SPOT_CONFIG_PATH,
        strategy_config: Annotated[
            Path,
            typer.Option(
                "--strategy-config",
                exists=True,
                dir_okay=False,
                readable=True,
            ),
        ] = DEFAULT_SPOT_STRATEGY_CONFIG_PATH,
        mode: SpotScannerMode = typer.Option(
            SpotScannerMode.ELIGIBLE,
            "--mode",
            case_sensitive=False,
        ),
        candle_limit: int = typer.Option(200, "--candles", min=60, max=1000),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Scan cash spot and admit approved long-only plans to the paper store."""

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            account_input = load_spot_live_account(account)
            product_config = load_spot_product_config(config)
            strategies = load_spot_strategy_config(strategy_config)
            with create_market_data_services(context.settings) as services:
                scan = scan_live_spot(
                    symbols=tuple(symbols.split(",")),
                    account_input=account_input,
                    candle_provider=services.candles,
                    ticker_provider=services.ticker,
                    product_config=product_config,
                    strategy_config=strategies,
                    mode=mode,
                    candle_limit=candle_limit,
                )
            store = _paper_store(context.settings.data_dir)
            summary = run_locked_paper_intake(
                market_type=IntakeMarketType.SPOT,
                data_dir=context.settings.data_dir,
                started_at=started_at,
                run=lambda: intake_spot_scan(
                    scan=scan,
                    store=store,
                    analysis_timestamp=started_at,
                ),
            )
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_summary(summary, output)


def _paper_store(data_dir: Path) -> PaperTradeStore:
    return PaperTradeStore(data_dir / "paper_trading" / "trades.json")


def _emit_summary(summary: IntakeSummary, output: str) -> None:
    normalized = output.strip().lower()
    payload = intake_summary_payload(summary)
    if normalized == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    if normalized != "text":
        raise typer.BadParameter("output must be text or json")
    typer.echo(
        f"PAPER_INTAKE_{summary.market_type.value.upper()} "
        f"| observed={summary.candidates_observed} "
        f"| accepted={summary.accepted} "
        f"| rejected={summary.rejected} "
        f"| duplicates={summary.duplicates_skipped} "
        f"| persistence_failures={summary.persistence_failures}"
    )
    if summary.reason_counts:
        typer.echo(
            "REASONS | "
            + " | ".join(
                f"{reason}={count}" for reason, count in summary.reason_counts.items()
            )
        )
    if summary.created_trade_ids:
        typer.echo("CREATED | " + ",".join(summary.created_trade_ids))
