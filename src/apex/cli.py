"""Apex command-line interface."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import NoReturn

import typer

from apex import __version__
from apex.application import (
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

app = typer.Typer(help="Apex Trading Agent command line interface.", no_args_is_help=True)


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
