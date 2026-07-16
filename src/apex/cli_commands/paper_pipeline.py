"""Combined automatic intake and lifecycle paper pipeline commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any

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
from apex.application.paper_intake import append_intake_log, intake_futures_scan, intake_spot_scan
from apex.application.paper_lifecycle_analytics import (
    build_paper_lifecycle_analytics,
    paper_lifecycle_analytics_payload,
)
from apex.application.paper_pipeline import (
    PaperPipelineResult,
    paper_pipeline_payload,
    run_locked_paper_pipeline,
)
from apex.application.paper_pipeline_diagnostics import build_futures_pipeline_diagnostics
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
from apex.paper_trading import (
    IntakeMarketType,
    IntakeSummary,
    PaperCycleAlreadyRunningError,
    PaperTrade,
    PaperTradeConfig,
    PaperTradeStore,
    ScheduledPaperCycleResult,
    run_scheduled_paper_cycle,
)
from apex.cli_commands.registration import remove_registered_commands
from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.paper import render_paper_pipeline


def register_paper_pipeline_commands(app: typer.Typer) -> None:
    """Register scheduler-safe combined paper pipeline commands."""

    @app.command("scheduled-futures-pipeline")
    def scheduled_futures_pipeline(
        symbols_file: Path = typer.Option(Path("config/symbols.yaml"), "--symbols-file"),
        risk_mode: RiskMode = typer.Option(
            RiskMode.STANDARD,
            "--risk-mode",
            case_sensitive=False,
        ),
        wallet_balance: float = typer.Option(100.0, "--wallet-balance", min=0.01),
        analysis_candles: int = typer.Option(200, "--analysis-candles", min=40, max=999),
        lifecycle_timeframe: str = typer.Option("5m", "--lifecycle-timeframe"),
        lifecycle_candles: int = typer.Option(80, "--lifecycle-candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy text or json output selector.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Run futures intake and lifecycle advancement under one pipeline lock."""

        selected_format = format_ or output
        try:
            normalize_output_mode(selected_format)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        started_at = datetime.now(UTC)
        diagnostics: dict[str, Any] = {}
        try:
            context = bootstrap()
            symbols = load_symbols(symbols_file)
            risk_config = load_default_risk_config()
            account = build_futures_account_input(
                wallet_balance=wallet_balance,
                risk_mode=risk_mode,
            )
            store = _paper_store(context.settings.data_dir)
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
                    candle_limit=analysis_candles + 1,
                    risk_config=risk_config,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                )
                diagnostics = build_futures_pipeline_diagnostics(scan)

                def run_futures_intake() -> IntakeSummary:
                    summary = intake_futures_scan(
                        scan=scan,
                        store=store,
                        plan_builder=lambda analysis: (
                            build_futures_plan_result(analysis.assessment.setup, account)
                            if analysis.assessment.setup is not None
                            else None
                        ),
                        source_command="paper scheduled-futures-pipeline",
                    )
                    append_intake_log(
                        context.settings.data_dir
                        / "paper_trading"
                        / "scheduler"
                        / "intake-futures.jsonl",
                        started_at=started_at,
                        summary=summary,
                        diagnostics=diagnostics,
                    )
                    return summary

                result = run_locked_paper_pipeline(
                    market_type=IntakeMarketType.FUTURES,
                    data_dir=context.settings.data_dir,
                    started_at=started_at,
                    stale_after=timedelta(minutes=stale_lock_minutes),
                    run_intake=run_futures_intake,
                    run_cycle=lambda: run_scheduled_paper_cycle(
                        store=store,
                        provider=services.candles,
                        market_type="futures",
                        timeframe=lifecycle_timeframe,
                        candle_limit=lifecycle_candles,
                        lock_path=_cycle_lock(context.settings.data_dir, "futures"),
                        log_path=_cycle_log(context.settings.data_dir, "futures"),
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        stale_lock_after=timedelta(minutes=stale_lock_minutes),
                        config=PaperTradeConfig(),
                    ),
                    diagnostics=diagnostics,
                    build_lifecycle_analytics=lambda intake, cycle: _build_lifecycle_payload(
                        intake,
                        cycle,
                        store,
                        IntakeMarketType.FUTURES,
                    ),
                )
        except PaperCycleAlreadyRunningError as exc:
            _emit_skipped_pipeline("futures", str(exc), selected_format)
            raise typer.Exit(code=0) from exc
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_pipeline(result, selected_format, diagnostics=diagnostics)

    @app.command("scheduled-spot-pipeline")
    def scheduled_spot_pipeline(
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
        analysis_candles: int = typer.Option(200, "--analysis-candles", min=60, max=1000),
        lifecycle_timeframe: str = typer.Option("5m", "--lifecycle-timeframe"),
        lifecycle_candles: int = typer.Option(80, "--lifecycle-candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        output: str = typer.Option(
            "text",
            "--output",
            "-o",
            help="Legacy text or json output selector.",
        ),
        format_: str | None = typer.Option(
            None,
            "--format",
            help="Presentation format: text, json, verbose, or debug.",
        ),
    ) -> None:
        """Run spot intake and lifecycle advancement under one pipeline lock."""

        selected_format = format_ or output
        try:
            normalize_output_mode(selected_format)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc

        started_at = datetime.now(UTC)
        try:
            context = bootstrap()
            account_input = load_spot_live_account(account)
            product_config = load_spot_product_config(config)
            strategies = load_spot_strategy_config(strategy_config)
            store = _paper_store(context.settings.data_dir)
            with create_market_data_services(context.settings) as services:
                scan = scan_live_spot(
                    symbols=tuple(symbols.split(",")),
                    account_input=account_input,
                    candle_provider=services.candles,
                    ticker_provider=services.ticker,
                    product_config=product_config,
                    strategy_config=strategies,
                    mode=mode,
                    candle_limit=analysis_candles,
                )
                result = run_locked_paper_pipeline(
                    market_type=IntakeMarketType.SPOT,
                    data_dir=context.settings.data_dir,
                    started_at=started_at,
                    stale_after=timedelta(minutes=stale_lock_minutes),
                    run_intake=lambda: intake_spot_scan(
                        scan=scan,
                        store=store,
                        analysis_timestamp=started_at,
                        source_command="paper scheduled-spot-pipeline",
                    ),
                    run_cycle=lambda: run_scheduled_paper_cycle(
                        store=store,
                        provider=services.candles,
                        market_type="spot",
                        timeframe=lifecycle_timeframe,
                        candle_limit=lifecycle_candles,
                        lock_path=_cycle_lock(context.settings.data_dir, "spot"),
                        log_path=_cycle_log(context.settings.data_dir, "spot"),
                        started_at=started_at,
                        completed_at=datetime.now(UTC),
                        stale_lock_after=timedelta(minutes=stale_lock_minutes),
                        config=PaperTradeConfig(),
                    ),
                    build_lifecycle_analytics=lambda intake, cycle: _build_lifecycle_payload(
                        intake,
                        cycle,
                        store,
                        IntakeMarketType.SPOT,
                    ),
                )
        except PaperCycleAlreadyRunningError as exc:
            _emit_skipped_pipeline("spot", str(exc), selected_format)
            raise typer.Exit(code=0) from exc
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_pipeline(result, selected_format)

    remove_registered_commands(app, {"scheduled-spot-pipeline"})


def _paper_store(data_dir: Path) -> PaperTradeStore:
    return PaperTradeStore(data_dir / "paper_trading" / "trades.json")


def _cycle_lock(data_dir: Path, market_type: str) -> Path:
    return data_dir / "paper_trading" / "scheduler" / "locks" / f"{market_type}.lock"


def _cycle_log(data_dir: Path, market_type: str) -> Path:
    return data_dir / "paper_trading" / "scheduler" / "logs" / f"{market_type}.jsonl"


def _build_lifecycle_payload(
    intake: IntakeSummary,
    cycle: ScheduledPaperCycleResult,
    store: PaperTradeStore,
    market_type: IntakeMarketType,
) -> dict[str, Any]:
    trades = _market_trades(store.load(), market_type)
    analytics = build_paper_lifecycle_analytics(
        intake=intake,
        runtime=cycle.runtime,
        trades=trades,
    )
    return paper_lifecycle_analytics_payload(analytics)


def _market_trades(
    trades: tuple[PaperTrade, ...],
    market_type: IntakeMarketType,
) -> tuple[PaperTrade, ...]:
    return tuple(
        trade
        for trade in trades
        if str(trade.analysis_payload.get("market_type", "futures")).strip().lower()
        == market_type.value
    )


def _emit_skipped_pipeline(market_type: str, reason: str, output: str) -> None:
    output_mode = normalize_output_mode(output)
    payload: dict[str, object] = {
        "market_type": market_type,
        "outcome": "skipped",
        "reason": reason,
        "intake": {},
        "cycle": {},
        "lifecycle_analytics": {},
    }
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(render_paper_pipeline(payload, mode=output_mode))


def _emit_pipeline(
    result: PaperPipelineResult,
    output: str,
    *,
    diagnostics: dict[str, Any] | None = None,
) -> None:
    output_mode = normalize_output_mode(output)
    payload = paper_pipeline_payload(result)
    payload["outcome"] = "completed"
    if diagnostics:
        payload["diagnostics"] = diagnostics
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(render_paper_pipeline(payload, mode=output_mode))
