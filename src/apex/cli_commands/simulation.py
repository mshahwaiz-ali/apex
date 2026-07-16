"""Professional current-setup futures simulation command."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

import typer

from apex.application import (
    analyze_symbol,
    bootstrap,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
)
from apex.backtesting import BacktestConfig, signal_from_setup, simulate_trade, summarize_trades
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import OutputMode, normalize_output_mode
from apex.presentation.simulation import render_futures_simulation


def register_simulation_command(app: typer.Typer) -> None:
    """Register the trader-facing current-setup simulation command."""

    @app.command("simulate-current-setup")
    def simulate_current_setup(
        symbol: Annotated[
            str,
            typer.Argument(help="One provider-supported futures market symbol."),
        ],
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text, json, verbose, or debug"),
        ] = "text",
        candle_limit: Annotated[
            int,
            typer.Option("--candles", min=80, max=1000),
        ] = 240,
        replay_timeframe: Annotated[
            str,
            typer.Option("--replay-timeframe"),
        ] = "5m",
    ) -> None:
        """Simulate one currently approved futures setup over fetched candles."""

        try:
            output_mode = normalize_output_mode(output)
            canonical = normalize_market_symbol(symbol)
            context = bootstrap()
            risk_config = load_default_risk_config()
            with create_market_data_services(context.settings) as services:
                analysis = analyze_symbol(
                    canonical,
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
                    gainer_state_thresholds=getattr(
                        context.settings,
                        "gainer_state_thresholds",
                        None,
                    ),
                )
                if analysis.assessment.setup is None:
                    payload: dict[str, object] = {
                        "symbol": canonical,
                        "decision": "NO_BACKTEST",
                        "reasons": list(analysis.assessment.reasons),
                    }
                    _emit(payload, output_mode)
                    return
                signal = signal_from_setup(analysis.assessment.setup)
                candles = services.candles.fetch_candles(
                    canonical,
                    replay_timeframe,
                    limit=candle_limit,
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Simulation market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        trade = simulate_trade(signal, candles, config=BacktestConfig())
        report = summarize_trades((trade,))
        payload = {
            "trade": _jsonable(asdict(trade)),
            "metrics": _jsonable(asdict(report) | {"trades": []}),
        }
        _emit(payload, output_mode)


def _emit(payload: dict[str, object], output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True))
        return
    typer.echo(render_futures_simulation(payload, mode=output_mode))


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


__all__ = ["register_simulation_command"]
