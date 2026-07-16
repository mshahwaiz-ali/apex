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
    resolve_futures_symbols,
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
from apex.cli_commands.registration import remove_registered_commands
from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.paper_progress import render_paper_intake


def register_paper_intake_commands(app: typer.Typer) -> None:
    """Register automatic paper opportunity intake commands."""

    @app.command("intake-futures")
    def intake_futures(
        symbols_file: Path | None = typer.Option(
            None,
            "--symbols-file",
            exists=True,
            dir_okay=False,
            readable=True,
            help="Optional static symbol override. Defaults to live Binance futures discovery.",
        ),
        risk_mode: RiskMode = typer.Option(RiskMode.STANDARD, "--risk-mode"),
        wallet_balance: float = typer.Option(100.0, "--wallet-balance", min=0.01),
        candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy output selector: text or json.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Scan futures and admit approved actionable plans to the paper store."""

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            risk_config = load_default_risk_config()
            account = build_futures_account_input(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
            )
            with create_market_data_services(context.settings) as services:
                symbols = resolve_futures_symbols(
                    services.futures_universe,
                    symbols_file=symbols_file,
                )
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
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
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
        _emit_summary(summary, output=output, format_=format_)

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
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy output selector: text or json.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
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
        _emit_summary(summary, output=output, format_=format_)

    remove_registered_commands(app, {"intake-spot"})


def _paper_store(data_dir: Path) -> PaperTradeStore:
    return PaperTradeStore(data_dir / "paper_trading" / "trades.json")


def _emit_summary(
    summary: IntakeSummary,
    *,
    output: str,
    format_: str | None,
) -> None:
    payload = intake_summary_payload(summary)
    try:
        mode = _resolve_presentation_mode(output=output, format_=format_)
    except ValueError as exc:
        raise typer.BadParameter(str(exc), param_hint="--format") from exc

    if mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return

    typer.echo(render_paper_intake(payload, mode=mode))


def _resolve_presentation_mode(*, output: str, format_: str | None) -> OutputMode:
    if format_ is not None:
        return normalize_output_mode(format_)

    legacy = output.strip().lower()
    if legacy not in {"text", "json"}:
        raise ValueError("legacy output must be text or json")
    return normalize_output_mode(legacy)
