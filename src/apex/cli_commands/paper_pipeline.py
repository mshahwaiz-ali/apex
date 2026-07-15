"""Combined automatic intake and lifecycle paper pipeline commands."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
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
from apex.application.paper_intake import intake_futures_scan, intake_spot_scan
from apex.application.paper_pipeline import (
    PaperPipelineResult,
    paper_pipeline_payload,
    run_locked_paper_pipeline,
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
from apex.paper_trading import (
    IntakeMarketType,
    PaperCycleAlreadyRunningError,
    PaperTradeConfig,
    PaperTradeStore,
    run_scheduled_paper_cycle,
)


def register_paper_pipeline_commands(app: typer.Typer) -> None:
    """Register scheduler-safe combined paper pipeline commands."""

    @app.command("scheduled-futures-pipeline")
    def scheduled_futures_pipeline(
        symbols_file: Path = typer.Option(Path("config/symbols.yaml"), "--symbols-file"),
        mode: str = typer.Option("normal", "--mode", help="normal, gainers, or all"),
        risk_mode: RiskMode = typer.Option(
            RiskMode.STANDARD,
            "--risk-mode",
            case_sensitive=False,
        ),
        wallet_balance: float = typer.Option(100.0, "--wallet-balance", min=0.01),
        analysis_candles: int = typer.Option(200, "--analysis-candles", min=40, max=1000),
        lifecycle_timeframe: str = typer.Option("5m", "--lifecycle-timeframe"),
        lifecycle_candles: int = typer.Option(80, "--lifecycle-candles", min=1, max=1000),
        stale_lock_minutes: int = typer.Option(30, "--stale-lock-minutes", min=1),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Run futures intake and lifecycle advancement under one pipeline lock."""

        started_at = datetime.now(UTC)
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
                    candle_limit=analysis_candles,
                    risk_config=risk_config,
                    scanner_mode=mode,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    gainer_state_thresholds=getattr(
                        context.settings,
                        "gainer_state_thresholds",
                        None,
                    ),
                )
                result = run_locked_paper_pipeline(
                    market_type=IntakeMarketType.FUTURES,
                    data_dir=context.settings.data_dir,
                    started_at=started_at,
                    stale_after=timedelta(minutes=stale_lock_minutes),
                    run_intake=lambda: intake_futures_scan(
                        scan=scan,
                        store=store,
                        plan_builder=lambda analysis: (
                            build_futures_plan_result(analysis.assessment.setup, account)
                            if analysis.assessment.setup is not None
                            else None
                        ),
                        source_command="paper scheduled-futures-pipeline",
                    ),
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
                )
        except PaperCycleAlreadyRunningError as exc:
            typer.echo(f"PAPER_PIPELINE_SKIPPED | market=futures | reason={exc}")
            raise typer.Exit(code=0) from exc
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_pipeline(result, output)

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
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
    ) -> None:
        """Run spot intake and lifecycle advancement under one pipeline lock."""

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
                )
        except PaperCycleAlreadyRunningError as exc:
            typer.echo(f"PAPER_PIPELINE_SKIPPED | market=spot | reason={exc}")
            raise typer.Exit(code=0) from exc
        except (FileNotFoundError, OSError, TypeError, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        _emit_pipeline(result, output)


def _paper_store(data_dir: Path) -> PaperTradeStore:
    return PaperTradeStore(data_dir / "paper_trading" / "trades.json")


def _cycle_lock(data_dir: Path, market_type: str) -> Path:
    return data_dir / "paper_trading" / "scheduler" / "locks" / f"{market_type}.lock"


def _cycle_log(data_dir: Path, market_type: str) -> Path:
    return data_dir / "paper_trading" / "scheduler" / "logs" / f"{market_type}.jsonl"


def _emit_pipeline(result: PaperPipelineResult, output: str) -> None:
    normalized = output.strip().lower()
    payload = paper_pipeline_payload(result)
    if normalized == "json":
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    if normalized != "text":
        raise typer.BadParameter("output must be text or json")
    runtime = result.cycle.runtime
    typer.echo(
        f"PAPER_PIPELINE_{result.market_type.value.upper()} "
        f"| observed={result.intake.candidates_observed} "
        f"| accepted={result.intake.accepted} "
        f"| rejected={result.intake.rejected} "
        f"| duplicates={result.intake.duplicates_skipped} "
        f"| eligible={runtime.cycle.eligible_trade_count} "
        f"| advanced={runtime.cycle.advanced_trade_count} "
        f"| unchanged={runtime.cycle.unchanged_trade_count} "
        f"| provider_failures={len(runtime.provider_failures)} "
        f"| log={result.log_path}"
    )
