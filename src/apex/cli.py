"""Apex command-line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import NoReturn

import typer

from apex import __version__
from apex.application import (
    SymbolAnalysis,
    analyze_symbol,
    bootstrap,
    build_analysis_record,
    build_futures_account_input,
    build_futures_plan_result,
    create_market_data_services,
    format_scan_text,
    format_symbol_text,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
    serialize_symbol_analysis,
    write_analysis_record,
    write_json_report,
)
from apex.application.analysis_records import write_analysis_record_sqlite
from apex.backtesting import (
    MAXIMUM_DATASET_CANDLES,
    BacktestConfig,
    FuturesDatasetSplitRatios,
    acquire_futures_dataset,
    load_and_verify_futures_dataset_split,
    load_futures_dataset,
    load_futures_dataset_campaign_plan,
    plan_futures_dataset_campaign,
    signal_from_setup,
    simulate_trade,
    split_futures_dataset,
    summarize_trades,
    write_futures_dataset,
    write_futures_dataset_campaign_plan,
    write_futures_dataset_split_manifest,
)
from apex.config import load_settings
from apex.data.providers.errors import MarketDataProviderError
from apex.execution import (
    EXECUTION_AUDIT_SCHEMA_VERSION,
    ExecutionAdapterSnapshot,
    ExecutionConfig,
    ExecutionEnvironment,
    ExecutionReconciliationRecord,
    ExecutionReconciliationReport,
    ExecutionReconciliationStatus,
    KillSwitchState,
    build_execution_readiness_report,
    intent_from_setup,
    load_duplicate_keys,
    preview_execution,
    readiness_report_payload,
    reconcile_execution_audit,
    reconciliation_report_payload,
    simulate_testnet_order,
)
from apex.intelligence import disabled_intelligence_metadata
from apex.optimization import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    WalkForwardSplit,
    calibration_to_payload,
    compare_performance,
    evaluate_performance,
    evaluate_walk_forward_calibration,
    load_performance_report,
    result_to_payload,
    save_optimization_result,
)
from apex.paper_trading import (
    PaperTrade,
    PaperTradeConfig,
    PaperTradeStore,
    build_paper_replay_report,
    create_paper_trade,
    summarize_paper_trades,
    update_paper_trade,
)

app = typer.Typer(help="Apex Trading Agent command line interface.", no_args_is_help=True)
paper_app = typer.Typer(help="Local paper-trading commands.", no_args_is_help=True)
optimize_app = typer.Typer(help="Framework-first optimization commands.", no_args_is_help=True)
intelligence_app = typer.Typer(
    help="Optional deterministic market-intelligence commands.",
    no_args_is_help=True,
)
execute_app = typer.Typer(help="Testnet-only execution commands.", no_args_is_help=True)
kill_switch_app = typer.Typer(help="Execution kill-switch commands.", no_args_is_help=True)
dataset_app = typer.Typer(
    help="Reproducible historical dataset commands.",
    no_args_is_help=True,
)
app.add_typer(paper_app, name="paper")
app.add_typer(optimize_app, name="optimize")
app.add_typer(intelligence_app, name="intelligence")
app.add_typer(execute_app, name="execute")
app.add_typer(dataset_app, name="dataset")
execute_app.add_typer(kill_switch_app, name="kill-switch")


@app.command()
def version() -> None:
    """Print the installed Apex version."""

    typer.echo(__version__)


@app.command("validate-config")
def validate_config(
    config_dir: Path = typer.Option(Path("config"), exists=True, file_okay=False),  # noqa: B008
) -> None:
    """Validate the default Apex configuration."""

    settings = load_settings(config_dir)
    typer.echo(json.dumps(settings.model_dump(mode="json"), indent=2))


@app.command()
def smoke() -> None:
    """Run a minimal end-to-end application bootstrap check."""

    context = bootstrap()
    typer.echo(
        json.dumps(
            {
                "status": "ok",
                "version": __version__,
                "environment": context.settings.environment,
            },
            indent=2,
        )
    )


def _exit_for_provider_error(prefix: str, error: MarketDataProviderError) -> NoReturn:
    typer.echo(f"{prefix}: {error}", err=True)
    raise typer.Exit(code=1) from error


@app.command("fetch")
def fetch_candles(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    timeframe: str = typer.Option("15m", "--timeframe", "-t"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=1000),
) -> None:
    """Fetch live public OHLCV candles from the configured provider."""

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            candles = services.candles.fetch_candles(
                symbol=symbol,
                timeframe=timeframe,
                limit=limit,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Market-data request failed", exc)

    typer.echo(
        json.dumps(
            [candle.model_dump(mode="json") for candle in candles],
            indent=2,
        )
    )


@app.command("ticker")
def ticker(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
) -> None:
    """Fetch the current public market ticker from the configured provider."""

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            snapshot = services.ticker.fetch_ticker(symbol)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Ticker request failed", exc)

    typer.echo(json.dumps(snapshot.model_dump(mode="json"), indent=2))


@app.command("analyze")
def analyze(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        help="Optional JSON report path.",
    ),
    record: Path | None = typer.Option(  # noqa: B008
        None,
        "--record",
        help="Optional append-only JSONL analysis record path.",
    ),
    record_db: Path | None = typer.Option(  # noqa: B008
        None,
        "--record-db",
        help="Optional SQLite analysis record database path.",
    ),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Run complete deterministic analysis for one symbol."""

    try:
        context = bootstrap()
        risk_config = load_default_risk_config()
        with create_market_data_services(context.settings) as services:
            analysis = analyze_symbol(
                symbol,
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
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Analysis market-data request failed", exc)

    payload = serialize_symbol_analysis(analysis)
    if report is not None:
        write_json_report(payload, report)
    if record is not None or record_db is not None:
        analysis_record = build_analysis_record(payload)
        if record is not None:
            write_analysis_record(record, analysis_record)
        if record_db is not None:
            write_analysis_record_sqlite(record_db, analysis_record)
    _emit_output(payload, format_symbol_text(analysis), output)


@app.command("scan")
def scan(
    symbols_file: Path = typer.Option(  # noqa: B008
        Path("config/symbols.yaml"),
        "--symbols-file",
    ),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        help="Optional JSON report path.",
    ),
    record: Path | None = typer.Option(  # noqa: B008
        None,
        "--record",
        help="Optional append-only JSONL scan record path.",
    ),
    record_db: Path | None = typer.Option(  # noqa: B008
        None,
        "--record-db",
        help="Optional SQLite scan record database path.",
    ),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
    mode: str = typer.Option("normal", "--mode", help="normal, gainers, or all"),
) -> None:
    """Analyze the configured symbol universe and rank opportunities."""

    try:
        symbols = load_symbols(symbols_file)
        context = bootstrap()
        risk_config = load_default_risk_config()
        with create_market_data_services(context.settings) as services:
            result = scan_symbols(
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
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Scanner market-data request failed", exc)

    payload = serialize_scan_result(result)
    if report is not None:
        write_json_report(payload, report)
    if record is not None or record_db is not None:
        analysis_record = build_analysis_record(payload)
        if record is not None:
            write_analysis_record(record, analysis_record)
        if record_db is not None:
            write_analysis_record_sqlite(record_db, analysis_record)
    _emit_output(payload, format_scan_text(result), output)


@dataset_app.command("acquire")
def dataset_acquire(
    symbol: str = typer.Argument(
        ...,
        help="Trading pair, for example BTC/USDT.",
    ),
    timeframe: str = typer.Option(
        "5m",
        "--timeframe",
        "-t",
        help="Historical candle timeframe.",
    ),
    candle_limit: int = typer.Option(
        1_000,
        "--candles",
        "-c",
        min=1,
        max=MAXIMUM_DATASET_CANDLES,
        help="Maximum provider candles to request.",
    ),
    output_file: Path = typer.Option(  # noqa: B008
        ...,
        "--output-file",
        "-f",
        dir_okay=False,
        help="Destination dataset JSON file.",
    ),
    dataset_id: str | None = typer.Option(
        None,
        "--dataset-id",
        help="Optional stable dataset identifier.",
    ),
) -> None:
    """Acquire and verify one reproducible historical futures dataset."""

    extracted_at = datetime.now(UTC)

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            dataset = acquire_futures_dataset(
                provider=services.candles,
                symbol=symbol,
                timeframe=timeframe,
                candle_limit=candle_limit,
                extracted_at=extracted_at,
                dataset_id=dataset_id,
            )

        write_futures_dataset(output_file, dataset)
        verified = load_futures_dataset(output_file)
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Dataset acquisition failed", exc)

    manifest = verified.manifest
    typer.echo(
        "DATASET_ACQUIRED "
        f"| id={manifest.dataset_id} "
        f"| symbol={manifest.symbol} "
        f"| timeframe={manifest.timeframe} "
        f"| candles={manifest.candle_count} "
        f"| start={manifest.start_time.isoformat()} "
        f"| end={manifest.end_time.isoformat()} "
        f"| hash={manifest.content_hash} "
        f"| file={output_file}"
    )


@dataset_app.command("campaign-plan")
def dataset_campaign_plan(
    campaign_id: str = typer.Option(
        ...,
        "--campaign-id",
        help="Stable campaign identifier.",
    ),
    symbols_file: Path = typer.Option(  # noqa: B008
        Path("config/symbols.yaml"),
        "--symbols-file",
        exists=True,
        dir_okay=False,
        readable=True,
        help="YAML symbol-universe file.",
    ),
    timeframe: str = typer.Option(
        "5m",
        "--timeframe",
        "-t",
        help="Historical candle timeframe for every job.",
    ),
    candle_count: int = typer.Option(
        1_000,
        "--candles",
        "-c",
        min=1,
        max=MAXIMUM_DATASET_CANDLES,
        help="Provider candle limit for every parent dataset.",
    ),
    provider: str = typer.Option(
        "binance",
        "--provider",
        help="Expected market-data provider identifier.",
    ),
    output_directory: Path = typer.Option(  # noqa: B008
        Path("data/datasets/futures"),
        "--output-dir",
        file_okay=False,
        help="Directory containing expected campaign artifacts.",
    ),
    train_ratio: float = typer.Option(
        0.60,
        "--train-ratio",
        help="Chronological train ratio.",
    ),
    validation_ratio: float = typer.Option(
        0.20,
        "--validation-ratio",
        help="Chronological validation ratio.",
    ),
    test_ratio: float = typer.Option(
        0.20,
        "--test-ratio",
        help="Chronological final-test ratio.",
    ),
    manifest_output: Path = typer.Option(  # noqa: B008
        ...,
        "--manifest-output",
        dir_okay=False,
        help="Destination campaign-plan manifest JSON file.",
    ),
) -> None:
    """Plan and verify a deterministic historical dataset campaign."""

    try:
        plan = plan_futures_dataset_campaign(
            campaign_id=campaign_id,
            symbols=tuple(load_symbols(symbols_file)),
            timeframe=timeframe,
            provider=provider,
            candle_count=candle_count,
            output_directory=output_directory,
            split_ratios=FuturesDatasetSplitRatios(
                train=train_ratio,
                validation=validation_ratio,
                final_test=test_ratio,
            ),
            reserved_output_paths=(manifest_output,),
        )
        write_futures_dataset_campaign_plan(manifest_output, plan)
        verified = load_futures_dataset_campaign_plan(manifest_output)
    except (KeyError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(
        "DATASET_CAMPAIGN_PLANNED "
        f"| campaign_id={verified.campaign_id} "
        f"| jobs={len(verified.jobs)} "
        f"| timeframe={verified.timeframe} "
        f"| candles={verified.candle_count} "
        f"| provider={verified.provider} "
        f"| manifest={manifest_output}"
    )


@dataset_app.command("split")
def dataset_split(
    input_file: Path = typer.Option(  # noqa: B008
        ...,
        "--input",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Existing parent futures dataset JSON file.",
    ),
    train_output: Path = typer.Option(  # noqa: B008
        ...,
        "--train-output",
        dir_okay=False,
        help="Destination train dataset JSON file.",
    ),
    validation_output: Path = typer.Option(  # noqa: B008
        ...,
        "--validation-output",
        dir_okay=False,
        help="Destination validation dataset JSON file.",
    ),
    test_output: Path = typer.Option(  # noqa: B008
        ...,
        "--test-output",
        dir_okay=False,
        help="Destination final-test dataset JSON file.",
    ),
    manifest_output: Path = typer.Option(  # noqa: B008
        ...,
        "--manifest-output",
        dir_okay=False,
        help="Destination split-set manifest JSON file.",
    ),
    train_ratio: float = typer.Option(
        0.60,
        "--train-ratio",
        help="Chronological train ratio.",
    ),
    validation_ratio: float = typer.Option(
        0.20,
        "--validation-ratio",
        help="Chronological validation ratio.",
    ),
    test_ratio: float = typer.Option(
        0.20,
        "--test-ratio",
        help="Chronological final-test ratio.",
    ),
) -> None:
    """Split and verify one historical dataset chronologically."""

    output_paths = (
        train_output,
        validation_output,
        test_output,
        manifest_output,
    )
    if len(set(output_paths)) != len(output_paths):
        raise typer.BadParameter("dataset split output paths must be unique")
    if input_file in output_paths:
        raise typer.BadParameter("dataset split outputs cannot overwrite the input dataset")

    try:
        parent = load_futures_dataset(input_file)
        split_set = split_futures_dataset(
            parent,
            ratios=FuturesDatasetSplitRatios(
                train=train_ratio,
                validation=validation_ratio,
                final_test=test_ratio,
            ),
        )

        write_futures_dataset(train_output, split_set.train)
        write_futures_dataset(validation_output, split_set.validation)
        write_futures_dataset(test_output, split_set.final_test)
        write_futures_dataset_split_manifest(
            manifest_output,
            split_set.manifest,
        )

        verified_parent, verified_split_set = load_and_verify_futures_dataset_split(
            parent_path=input_file,
            train_path=train_output,
            validation_path=validation_output,
            final_test_path=test_output,
            manifest_path=manifest_output,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    manifest = verified_split_set.manifest
    typer.echo(
        "DATASET_SPLIT "
        f"| parent_id={verified_parent.manifest.dataset_id} "
        f"| parent_hash={verified_parent.manifest.content_hash} "
        f"| train_id={manifest.train_dataset_id} "
        f"| train_candles={manifest.train_candle_count} "
        f"| validation_id={manifest.validation_dataset_id} "
        f"| validation_candles={manifest.validation_candle_count} "
        f"| final_test_id={manifest.final_test_dataset_id} "
        f"| final_test_candles={manifest.final_test_candle_count} "
        f"| manifest={manifest_output}"
    )


@app.command("backtest")
def backtest(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    candle_limit: int = typer.Option(240, "--candles", min=80, max=1000),
    replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
) -> None:
    """Simulate the current approved setup over subsequent fetched candles."""

    try:
        context = bootstrap()
        risk_config = load_default_risk_config()
        with create_market_data_services(context.settings) as services:
            analysis = analyze_symbol(
                symbol,
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
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
            if analysis.assessment.setup is None:
                payload: dict[str, object] = {
                    "symbol": symbol,
                    "decision": "NO_BACKTEST",
                    "reasons": list(analysis.assessment.reasons),
                }
                _emit_output(payload, f"{symbol}: NO_BACKTEST | no approved setup", output)
                return
            signal = signal_from_setup(analysis.assessment.setup)
            candles = services.candles.fetch_candles(
                symbol,
                replay_timeframe,
                limit=candle_limit,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Backtest market-data request failed", exc)

    trade = simulate_trade(signal, candles, config=BacktestConfig())
    report = summarize_trades((trade,))
    payload = {
        "trade": _jsonable(asdict(trade)),
        "metrics": _jsonable(asdict(report) | {"trades": []}),
    }
    _emit_output(
        payload,
        (
            f"{symbol}: {trade.outcome.value.upper()} "
            f"| net_pnl={trade.net_pnl:.2f} "
            f"| r={trade.realized_r_multiple:.2f}"
        ),
        output,
    )


@paper_app.command("record")
def paper_record(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Analyze a symbol and record an approved setup as a paper trade."""

    try:
        context = bootstrap()
        risk_config = load_default_risk_config()
        with create_market_data_services(context.settings) as services:
            analysis = analyze_symbol(
                symbol,
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
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Paper record market-data request failed", exc)

    if analysis.assessment.setup is None:
        typer.echo(f"{symbol}: NO_PAPER_TRADE | no approved setup")
        return

    store = _paper_store(context.settings.data_dir)
    trade = create_paper_trade(
        analysis.assessment.setup,
        analysis_payload=serialize_symbol_analysis(analysis),
        futures_plan=build_futures_plan_result(
            analysis.assessment.setup,
            build_futures_account_input(wallet_balance=100.0),
        ),
    )
    store.upsert(trade)
    typer.echo(f"{symbol}: PAPER_RECORDED | id={trade.trade_id} | state={trade.state.value}")


@paper_app.command("update")
def paper_update(
    symbol: str | None = typer.Argument(None, help="Optional symbol filter."),
    timeframe: str = typer.Option("5m", "--timeframe"),
    candle_limit: int = typer.Option(80, "--candles", min=1, max=1000),
) -> None:
    """Update open paper trades with fresh candles."""

    try:
        context = bootstrap()
        store = _paper_store(context.settings.data_dir)
        trades = store.load()
        updated: list[PaperTrade] = []
        with create_market_data_services(context.settings) as services:
            for trade in trades:
                if symbol is not None and trade.signal.symbol != symbol:
                    updated.append(trade)
                    continue
                if not trade.is_open:
                    updated.append(trade)
                    continue
                candles = tuple(
                    services.candles.fetch_candles(
                        trade.signal.symbol,
                        timeframe,
                        limit=candle_limit,
                    )
                )
                updated.append(update_paper_trade(trade, candles, config=PaperTradeConfig()))
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Paper update market-data request failed", exc)

    store.save(tuple(updated))
    typer.echo(f"PAPER_UPDATED | trades={len(updated)}")


@paper_app.command("report")
def paper_report(
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Show current local paper-trading performance."""

    context = bootstrap()
    store = _paper_store(context.settings.data_dir)
    trades = store.load()
    performance = summarize_paper_trades(trades)
    payload = _jsonable(asdict(performance))
    text = (
        f"PAPER_REPORT | total={performance.total_trades} "
        f"| open={performance.open_trades} "
        f"| closed={performance.closed_trades} "
        f"| net_pnl={performance.net_pnl:.2f} "
        f"| win_rate={performance.win_rate:.2%}"
    )
    _emit_output(payload, text, output)


@paper_app.command("replay-report")
def paper_replay_report(
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        help="Optional JSON replay report path.",
    ),
) -> None:
    """Replay stored paper lifecycle events into an audit report."""

    context = bootstrap()
    store = _paper_store(context.settings.data_dir)
    payload = build_paper_replay_report(store.load())
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit_output(
        payload,
        f"PAPER_REPLAY_REPORT | replayed={payload['replayed_count']} "
        f"| failures={payload['failure_count']}",
        output,
    )


def _paper_store(data_dir: Path) -> PaperTradeStore:
    return PaperTradeStore(data_dir / "paper_trading" / "trades.json")


@optimize_app.command("evaluate")
def optimize_evaluate(
    input_path: Path = typer.Option(  # noqa: B008
        ...,
        "--input",
        exists=True,
        dir_okay=False,
    ),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Evaluate one performance report without changing config."""

    context = bootstrap()
    summary = load_performance_report(input_path)
    result = evaluate_performance(
        summary,
        run_config=OptimizationRunConfig(
            identifier="cli-evaluate",
            variable_group=OptimizationGroup.SCORING_THRESHOLDS,
        ),
    )
    report_path = context.settings.data_dir / "optimization" / "latest-evaluate.json"
    save_optimization_result(result, report_path)
    payload = result_to_payload(result) | {"report_path": str(report_path)}
    _emit_output(
        payload,
        f"OPTIMIZE_EVALUATE | decision={result.decision.value} | report={report_path}",
        output,
    )


@optimize_app.command("compare")
def optimize_compare(
    baseline: Path = typer.Option(  # noqa: B008
        ...,
        "--baseline",
        exists=True,
        dir_okay=False,
    ),
    candidate: Path = typer.Option(  # noqa: B008
        ...,
        "--candidate",
        exists=True,
        dir_okay=False,
    ),
    group: str = typer.Option(OptimizationGroup.SCORING_THRESHOLDS.value, "--group"),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Compare baseline and candidate performance reports."""

    context = bootstrap()
    group_value = OptimizationGroup(group)
    result = compare_performance(
        load_performance_report(baseline),
        load_performance_report(candidate),
        run_config=OptimizationRunConfig(
            identifier="cli-compare",
            variable_group=group_value,
        ),
        parameter_set=CandidateParameterSet(
            identifier="candidate-report",
            group=group_value,
            parameters={"source": str(candidate)},
        ),
    )
    report_path = context.settings.data_dir / "optimization" / "latest-compare.json"
    save_optimization_result(result, report_path)
    payload = result_to_payload(result) | {"report_path": str(report_path)}
    _emit_output(
        payload,
        f"OPTIMIZE_COMPARE | decision={result.decision.value} | report={report_path}",
        output,
    )


@optimize_app.command("calibrate")
def optimize_calibrate(
    train_baseline: Path = typer.Option(  # noqa: B008
        ...,
        "--train-baseline",
        exists=True,
        dir_okay=False,
    ),
    train_candidate: Path = typer.Option(  # noqa: B008
        ...,
        "--train-candidate",
        exists=True,
        dir_okay=False,
    ),
    validation_baseline: Path = typer.Option(  # noqa: B008
        ...,
        "--validation-baseline",
        exists=True,
        dir_okay=False,
    ),
    validation_candidate: Path = typer.Option(  # noqa: B008
        ...,
        "--validation-candidate",
        exists=True,
        dir_okay=False,
    ),
    final_test_baseline: Path | None = typer.Option(  # noqa: B008
        None,
        "--final-test-baseline",
        exists=True,
        dir_okay=False,
    ),
    final_test_candidate: Path | None = typer.Option(  # noqa: B008
        None,
        "--final-test-candidate",
        exists=True,
        dir_okay=False,
    ),
    group: str = typer.Option(OptimizationGroup.SCORING_THRESHOLDS.value, "--group"),
    parameter_id: str = typer.Option("candidate-report", "--parameter-id"),
    parameter_name: str = typer.Option("source", "--parameter-name"),
    parameter_value: str | None = typer.Option(None, "--parameter-value"),
    train_start: str = typer.Option(..., "--train-start"),
    train_end: str = typer.Option(..., "--train-end"),
    validation_start: str = typer.Option(..., "--validation-start"),
    validation_end: str = typer.Option(..., "--validation-end"),
    out_of_sample_start: str = typer.Option(..., "--out-of-sample-start"),
    out_of_sample_end: str = typer.Option(..., "--out-of-sample-end"),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Evaluate a train/validation calibration candidate without using final test for selection."""

    if (final_test_baseline is None) != (final_test_candidate is None):
        raise typer.BadParameter("final-test baseline and candidate must be provided together")
    context = bootstrap()
    group_value = OptimizationGroup(group)
    split = WalkForwardSplit(
        train_start=train_start,
        train_end=train_end,
        validation_start=validation_start,
        validation_end=validation_end,
        out_of_sample_start=out_of_sample_start,
        out_of_sample_end=out_of_sample_end,
    )
    run_config = OptimizationRunConfig(
        identifier="cli-calibrate",
        variable_group=group_value,
        split=split,
    )
    parameter_set = CandidateParameterSet(
        identifier=parameter_id,
        group=group_value,
        parameters={parameter_name: parameter_value or str(validation_candidate)},
    )
    evaluation = evaluate_walk_forward_calibration(
        split=split,
        run_config=run_config,
        parameter_set=parameter_set,
        train_baseline=load_performance_report(train_baseline),
        train_candidate=load_performance_report(train_candidate),
        validation_baseline=load_performance_report(validation_baseline),
        validation_candidate=load_performance_report(validation_candidate),
        final_test_baseline=(
            load_performance_report(final_test_baseline)
            if final_test_baseline is not None
            else None
        ),
        final_test_candidate=(
            load_performance_report(final_test_candidate)
            if final_test_candidate is not None
            else None
        ),
    )
    report_path = context.settings.data_dir / "optimization" / "latest-calibration.json"
    payload = calibration_to_payload(evaluation) | {"report_path": str(report_path)}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit_output(
        payload,
        f"OPTIMIZE_CALIBRATE | decision={evaluation.decision.value} | report={report_path}",
        output,
    )


@intelligence_app.command("summary")
def intelligence_summary(
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Show optional intelligence status without changing trade decisions."""

    context = bootstrap()
    enabled = context.settings.advanced_intelligence_enabled
    payload = (
        {
            "enabled": True,
            "funding_enabled": context.settings.intelligence_funding_enabled,
            "open_interest_enabled": context.settings.intelligence_open_interest_enabled,
            "correlation_enabled": context.settings.intelligence_correlation_enabled,
            "warnings": [],
        }
        if enabled
        else disabled_intelligence_metadata()
    )
    text = f"INTELLIGENCE_SUMMARY | enabled={str(enabled).lower()}"
    _emit_output(payload, text, output)


@execute_app.command("preview")
def execute_preview(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Preview local testnet-simulation intent without submitting anything."""

    analysis = _analysis_for_execution(symbol, candle_limit)
    if analysis.assessment.setup is None:
        _emit_output(
            {"symbol": symbol, "decision": "NO_EXECUTION", "reasons": analysis.assessment.reasons},
            f"{symbol}: NO_EXECUTION | no approved setup",
            output,
        )
        return
    result = preview_execution(intent_from_setup(analysis.assessment.setup))
    payload = _jsonable(asdict(result))
    _emit_output(payload, f"EXECUTE_PREVIEW | state={result.state.value}", output)


@execute_app.command("testnet")
def execute_testnet(
    symbol: str = typer.Argument(..., help="Trading pair, for example BTC/USDT."),
    confirm: bool = typer.Option(False, "--confirm", help="Required for local simulation."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Record a local testnet simulation event after explicit confirmation."""

    context = bootstrap()
    analysis = _analysis_for_execution(symbol, candle_limit)
    if analysis.assessment.setup is None:
        _emit_output(
            {"symbol": symbol, "decision": "NO_EXECUTION", "reasons": analysis.assessment.reasons},
            f"{symbol}: NO_EXECUTION | no approved setup",
            output,
        )
        return
    audit_log = _execution_audit_log(context.settings.data_dir)
    result = simulate_testnet_order(
        intent_from_setup(analysis.assessment.setup),
        config=ExecutionConfig(enabled=confirm, testnet=True),
        audit_log=audit_log,
        kill_switch=_read_kill_switch(context.settings.data_dir),
        confirmed=confirm,
        existing_duplicate_keys=load_duplicate_keys(audit_log),
    )
    _emit_output(
        _jsonable(asdict(result)),
        f"EXECUTE_LOCAL_TESTNET_SIMULATION | state={result.state.value}",
        output,
    )


@execute_app.command("status")
def execute_status(
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Show local execution safety status."""

    context = bootstrap()
    audit_log = _execution_audit_log(context.settings.data_dir)
    payload = {
        "mode": "local_testnet_simulation_only",
        "environment": ExecutionEnvironment.LOCAL_TESTNET_SIMULATION.value,
        "audit_schema_version": EXECUTION_AUDIT_SCHEMA_VERSION,
        "enabled_by_default": False,
        "live_fallback": False,
        "kill_switch": _read_kill_switch(context.settings.data_dir).value,
        "duplicate_keys": len(load_duplicate_keys(audit_log)),
        "audit_log": str(audit_log),
    }
    _emit_output(
        payload,
        "EXECUTE_STATUS | "
        f"mode=local_testnet_simulation_only | kill_switch={payload['kill_switch']}",
        output,
    )


@execute_app.command("reconcile")
def execute_reconcile(
    snapshots: Path | None = typer.Option(  # noqa: B008
        None,
        "--snapshots",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional JSON adapter snapshot file for deterministic reconciliation.",
    ),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        dir_okay=False,
        help="Optional JSON reconciliation report path.",
    ),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Reconcile local execution audit events against deterministic snapshots."""

    context = bootstrap()
    audit_log = _execution_audit_log(context.settings.data_dir)
    snapshot_items = _load_execution_snapshots(snapshots) if snapshots is not None else ()
    result = reconcile_execution_audit(
        audit_log,
        adapter_snapshots=snapshot_items,
        adapter_name="snapshot-file" if snapshots is not None else "local-simulation",
    )
    payload = reconciliation_report_payload(result)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit_output(
        payload,
        "EXECUTE_RECONCILE | "
        f"matched={result.matched_count} | missing={result.missing_count} "
        f"| mismatched={result.mismatched_count} | rejected={result.rejected_local_count}",
        output,
    )


@execute_app.command("readiness")
def execute_readiness(
    reconciliation: Path | None = typer.Option(  # noqa: B008
        None,
        "--reconciliation",
        exists=True,
        dir_okay=False,
        readable=True,
        help="Optional JSON report produced by execute reconcile.",
    ),
    report: Path | None = typer.Option(  # noqa: B008
        None,
        "--report",
        dir_okay=False,
        help="Optional JSON readiness report path.",
    ),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
) -> None:
    """Report local simulation readiness and explicit exchange blockers."""

    context = bootstrap()
    readiness = build_execution_readiness_report(
        audit_log=_execution_audit_log(context.settings.data_dir),
        kill_switch=_read_kill_switch(context.settings.data_dir),
        reconciliation=(
            _load_reconciliation_report(reconciliation) if reconciliation is not None else None
        ),
    )
    payload = readiness_report_payload(readiness)
    if report is not None:
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _emit_output(
        payload,
        "EXECUTE_READINESS | "
        f"local_simulation_ready={str(readiness.local_simulation_ready).lower()} "
        f"| exchange_ready={str(readiness.exchange_ready).lower()} "
        f"| blockers={len(readiness.blockers)}",
        output,
    )


@kill_switch_app.command("enable")
def execute_kill_switch_enable() -> None:
    """Enable the local execution kill switch."""

    context = bootstrap()
    _execution_kill_switch_path(context.settings.data_dir).write_text("enabled\n", encoding="utf-8")
    typer.echo("EXECUTION_KILL_SWITCH | enabled")


def _analysis_for_execution(symbol: str, candle_limit: int) -> SymbolAnalysis:
    try:
        context = bootstrap()
        risk_config = load_default_risk_config()
        with create_market_data_services(context.settings) as services:
            return analyze_symbol(
                symbol,
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
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Execution market-data request failed", exc)


def _execution_audit_log(data_dir: Path) -> Path:
    return data_dir / "execution" / "audit.jsonl"


def _load_execution_snapshots(path: Path) -> tuple[ExecutionAdapterSnapshot, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("orders", payload) if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise typer.BadParameter("execution snapshots must be a JSON list or orders object")
    try:
        return tuple(ExecutionAdapterSnapshot(**item) for item in items if isinstance(item, dict))
    except (TypeError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc


def _load_reconciliation_report(path: Path) -> ExecutionReconciliationReport:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise typer.BadParameter("reconciliation report must be a JSON object")
    try:
        records = tuple(
            ExecutionReconciliationRecord(
                status=ExecutionReconciliationStatus(str(item["status"])),
                audit_state=item["audit_state"],
                client_order_id=item.get("client_order_id"),
                local_order_id=item.get("local_order_id"),
                adapter_order_id=item.get("adapter_order_id"),
                reasons=tuple(str(reason) for reason in item.get("reasons", [])),
            )
            for item in payload.get("records", [])
            if isinstance(item, dict)
        )
        return ExecutionReconciliationReport(
            generated_at=_datetime_from_iso(str(payload["generated_at"])),
            audit_path=str(payload["audit_path"]),
            adapter_name=str(payload["adapter_name"]),
            total_audit_events=int(payload["total_audit_events"]),
            matched_count=int(payload["matched_count"]),
            missing_count=int(payload["missing_count"]),
            mismatched_count=int(payload["mismatched_count"]),
            rejected_local_count=int(payload["rejected_local_count"]),
            records=records,
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise typer.BadParameter(f"invalid reconciliation report: {exc}") from exc


def _datetime_from_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("datetime must be timezone-aware")
    return parsed


def _execution_kill_switch_path(data_dir: Path) -> Path:
    path = data_dir / "execution" / "kill_switch.txt"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_kill_switch(data_dir: Path) -> KillSwitchState:
    try:
        value = _execution_kill_switch_path(data_dir).read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return KillSwitchState.DISABLED
    return KillSwitchState.ENABLED if value == "enabled" else KillSwitchState.DISABLED


def _emit_output(payload: object, text: str, output: str) -> None:
    normalized = output.lower().strip()
    if normalized == "json":
        typer.echo(json.dumps(_jsonable(payload), indent=2, sort_keys=True))
        return
    if normalized != "text":
        raise typer.BadParameter("output must be text or json")
    typer.echo(text)


def _jsonable(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


if __name__ == "__main__":
    app()
