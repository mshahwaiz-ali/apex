"""Corrected Apex CLI surface layered over the existing command set."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

import typer

from apex.application import (
    ChronologicalBacktestRequest,
    analyze_selected_symbol,
    bootstrap,
    create_market_data_services,
    format_symbol_text,
    load_default_risk_config,
    normalize_market_symbol,
    run_chronological_pipeline_backtest,
    serialize_symbol_analysis,
)
from apex.cli import app
from apex.cli import backtest as simulate_current_setup
from apex.cli import fetch_candles as legacy_fetch_candles
from apex.cli import ticker as legacy_ticker
from apex.cli_overlay import remove_commands
from apex.data.providers.errors import MarketDataProviderError

remove_commands(app, {"fetch", "ticker", "analyze", "backtest"})


@app.command("fetch")
def fetch_candles(
    symbol: str = typer.Argument(..., help="Trading pair, including compact BTCUSDT form."),
    timeframe: str = typer.Option("15m", "--timeframe", "-t"),
    limit: int = typer.Option(10, "--limit", "-l", min=1, max=1000),
) -> None:
    """Fetch candles for any explicitly selected market symbol."""

    legacy_fetch_candles(normalize_market_symbol(symbol), timeframe, limit)


@app.command("ticker")
def ticker(symbol: str = typer.Argument(..., help="Trading pair, including compact BTCUSDT form.")) -> None:
    """Fetch a ticker for any explicitly selected market symbol."""

    legacy_ticker(normalize_market_symbol(symbol))


@app.command("analyze")
def analyze(
    symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
    output: str = typer.Option("text", "--output", "-o", help="text or json"),
    candle_limit: int = typer.Option(200, "--candles", min=40, max=1000),
) -> None:
    """Analyze one manually selected coin through the canonical symbol path."""

    try:
        context = bootstrap()
        with create_market_data_services(context.settings) as services:
            result = analyze_selected_symbol(
                symbol,
                services.candles,
                timeframes=context.settings.analysis_timeframes,
                timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                timeframe_max_staleness_seconds=getattr(
                    context.settings, "timeframe_max_staleness_seconds", None
                ),
                candle_limit=candle_limit,
                risk_config=load_default_risk_config(),
            )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        typer.echo(f"Analysis market-data request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    payload = serialize_symbol_analysis(result)
    typer.echo(json.dumps(payload, indent=2, default=str) if output == "json" else format_symbol_text(result))


app.command("simulate-current-setup")(simulate_current_setup)


@app.command("chronological-backtest")
def chronological_backtest(
    symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
    replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
    history_limit: int = typer.Option(500, "--history-candles", min=80, max=1000),
    candle_limit: int = typer.Option(200, "--analysis-candles", min=40, max=500),
) -> None:
    """Run the full pipeline repeatedly using historical candle prefixes only."""

    canonical = normalize_market_symbol(symbol)
    try:
        context = bootstrap()
        timeframes = tuple(dict.fromkeys((*context.settings.analysis_timeframes, replay_timeframe)))
        with create_market_data_services(context.settings) as services:
            candles = {
                timeframe: tuple(
                    services.candles.fetch_candles(canonical, timeframe, limit=history_limit)
                )
                for timeframe in timeframes
            }
        result = run_chronological_pipeline_backtest(
            ChronologicalBacktestRequest(
                symbol=canonical,
                candles_by_timeframe=candles,
                analysis_timeframes=tuple(context.settings.analysis_timeframes),
                replay_timeframe=replay_timeframe,
                candle_limit=candle_limit,
                risk_config=load_default_risk_config(),
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    except MarketDataProviderError as exc:
        typer.echo(f"Chronological backtest market-data request failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    payload: dict[str, Any] = {
        "symbol": canonical,
        "decision_count": result.decision_count,
        "approved_count": result.approved_count,
        "skipped_count": result.skipped_count,
        "failure_count": result.failure_count,
        "failures": dict(result.failures),
        "metrics": asdict(result.report),
        "trades": [asdict(trade) for trade in result.trades],
    }
    typer.echo(json.dumps(payload, indent=2, default=str))
