"""Apex command-line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import typer

from apex import __version__
from apex.application import (
    SymbolAnalysis,
    analyze_symbol,
    bootstrap,
    create_market_data_services,
    format_scan_text,
    format_symbol_text,
    load_default_risk_config,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
    serialize_symbol_analysis,
    write_json_report,
)
from apex.backtesting import BacktestConfig, signal_from_setup, simulate_trade, summarize_trades
from apex.config import load_settings
from apex.data.providers.errors import MarketDataProviderError
from apex.execution import (
    ExecutionConfig,
    KillSwitchState,
    intent_from_setup,
    load_duplicate_keys,
    preview_execution,
    submit_testnet_order,
)
from apex.intelligence import disabled_intelligence_metadata
from apex.optimization import (
    CandidateParameterSet,
    OptimizationGroup,
    OptimizationRunConfig,
    compare_performance,
    evaluate_performance,
    load_performance_report,
    result_to_payload,
    save_optimization_result,
)
from apex.paper_trading import (
    PaperTrade,
    PaperTradeConfig,
    PaperTradeStore,
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
app.add_typer(paper_app, name="paper")
app.add_typer(optimize_app, name="optimize")
app.add_typer(intelligence_app, name="intelligence")
app.add_typer(execute_app, name="execute")
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
                candle_limit=candle_limit,
                risk_config=risk_config,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Analysis market-data request failed", exc)

    payload = serialize_symbol_analysis(analysis)
    if report is not None:
        write_json_report(payload, report)
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
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
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
                candle_limit=candle_limit,
                risk_config=risk_config,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Scanner market-data request failed", exc)

    payload = serialize_scan_result(result)
    if report is not None:
        write_json_report(payload, report)
    _emit_output(payload, format_scan_text(result), output)


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
                candle_limit=candle_limit,
                risk_config=risk_config,
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
                candle_limit=candle_limit,
                risk_config=risk_config,
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
    """Preview testnet execution intent without submitting anything."""

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
    confirm: bool = typer.Option(False, "--confirm", help="Required for testnet submit."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Record a simulated testnet order after explicit confirmation."""

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
    result = submit_testnet_order(
        intent_from_setup(analysis.assessment.setup),
        config=ExecutionConfig(enabled=confirm, testnet=True),
        audit_log=audit_log,
        kill_switch=_read_kill_switch(context.settings.data_dir),
        confirmed=confirm,
        existing_duplicate_keys=load_duplicate_keys(audit_log),
    )
    _emit_output(
        _jsonable(asdict(result)),
        f"EXECUTE_TESTNET | state={result.state.value}",
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
        "mode": "testnet_only",
        "enabled_by_default": False,
        "kill_switch": _read_kill_switch(context.settings.data_dir).value,
        "duplicate_keys": len(load_duplicate_keys(audit_log)),
        "audit_log": str(audit_log),
    }
    _emit_output(
        payload,
        f"EXECUTE_STATUS | mode=testnet_only | kill_switch={payload['kill_switch']}",
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
                candle_limit=candle_limit,
                risk_config=risk_config,
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        _exit_for_provider_error("Execution market-data request failed", exc)


def _execution_audit_log(data_dir: Path) -> Path:
    return data_dir / "execution" / "audit.jsonl"


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
