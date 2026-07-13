"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from apex.application import (
    ChronologicalBacktestRequest,
    bootstrap,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    run_chronological_pipeline_backtest,
)
from apex.cli import backtest as legacy_simulate_current_setup
from apex.data.providers.errors import MarketDataProviderError


def register_backtesting_commands(app: typer.Typer) -> None:
    @app.command("simulate-current-setup")
    def simulate_current_setup(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        output: str = typer.Option("text", "--output", "-o", help="text or json"),
        candle_limit: int = typer.Option(240, "--candles", min=80, max=1000),
        replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
    ) -> None:
        """Simulate one currently approved setup using a canonical market symbol."""

        canonical = normalize_market_symbol(symbol)
        legacy_simulate_current_setup(
            symbol=canonical,
            output=output,
            candle_limit=candle_limit,
            replay_timeframe=replay_timeframe,
        )

    @app.command("chronological-backtest")
    def chronological_backtest(
        symbol: str = typer.Argument(..., help="Any provider-supported market symbol."),
        replay_timeframe: str = typer.Option("5m", "--replay-timeframe"),
        history_limit: int = typer.Option(500, "--history-candles", min=80, max=1000),
        candle_limit: int = typer.Option(200, "--analysis-candles", min=40, max=500),
    ) -> None:
        canonical = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            timeframes = tuple(
                dict.fromkeys((*context.settings.analysis_timeframes, replay_timeframe))
            )
            with create_market_data_services(context.settings) as services:
                candles = {
                    timeframe: tuple(
                        services.candles.fetch_candles(
                            canonical,
                            timeframe,
                            limit=history_limit,
                        )
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

        payload = {
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