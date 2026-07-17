"""Focused public chronological backtest command."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    create_market_data_services,
    normalize_market_symbol,
)
from apex.backtesting.contracts import BacktestConfig
from apex.backtesting.discovery_signal import signal_from_discovery_setup
from apex.backtesting.engine import simulate_trade, summarize_trades
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayProvider,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.presentation import OutputMode, normalize_cli_output_mode


def register_backtesting_commands(app: typer.Typer) -> None:
    """Register one leak-proof historical strategy-evaluation command."""

    @app.command("backtest")
    def backtest(
        symbol: Annotated[
            str,
            typer.Argument(help="Any provider-supported futures market symbol."),
        ],
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
        candle_limit: Annotated[
            int,
            typer.Option("--candles", min=80, max=900),
        ] = 240,
        replay_timeframe: Annotated[
            str,
            typer.Option("--replay-timeframe"),
        ] = "5m",
        replay_candles: Annotated[
            int,
            typer.Option("--replay-candles", min=1, max=100),
        ] = 24,
        config_dir: Annotated[
            Path,
            typer.Option(
                "--config-dir",
                exists=True,
                file_okay=False,
                help="Configuration directory containing Apex YAML settings.",
            ),
        ] = Path("config"),
    ) -> None:
        """Analyze a historical prefix and replay its setup on withheld candles."""

        try:
            output_mode = normalize_cli_output_mode(output)
            normalized_symbol = normalize_market_symbol(symbol)
            context = bootstrap(config_dir)
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            requested_timeframes = tuple(dict.fromkeys((*analysis_timeframes, replay_timeframe)))
            source_limit = candle_limit + replay_candles

            with create_market_data_services(context.settings) as services:
                series = tuple(
                    HistoricalCandleSeries(
                        symbol=normalized_symbol,
                        timeframe=timeframe,
                        candles=tuple(
                            candle
                            for candle in services.candles.fetch_candles(
                                normalized_symbol,
                                timeframe,
                                limit=source_limit,
                            )
                            if candle.is_closed
                        ),
                    )
                    for timeframe in requested_timeframes
                )

            replay_series = next(
                item for item in series if item.timeframe == replay_timeframe
            )
            if len(replay_series.candles) <= replay_candles:
                raise ValueError(
                    "backtest requires more closed source candles than the replay holdout"
                )

            decision_index = len(replay_series.candles) - replay_candles - 1
            decision_time = replay_series.candles[decision_index].close_time
            future_candles = tuple(
                candle
                for candle in replay_series.candles
                if candle.open_time >= decision_time
            )[:replay_candles]
            if not future_candles:
                raise ValueError("backtest replay holdout is empty")

            replay_provider = HistoricalReplayProvider(
                store=HistoricalCandleStore(series),
                decision_time=decision_time,
            )
            analysis = analyze_selected_symbol(
                normalized_symbol,
                replay_provider,
                timeframes=analysis_timeframes,
                timeframe_roles=getattr(context.settings, "timeframe_roles", None),
                timeframe_max_staleness_seconds=getattr(
                    context.settings,
                    "timeframe_max_staleness_seconds",
                    None,
                ),
                candle_limit=candle_limit,
                generated_at=decision_time,
                strategy_routing=getattr(context.settings, "strategy_routing", None),
            )
        except (StopIteration, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Backtest market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        setup = analysis.assessment.setup
        if setup is None:
            payload: dict[str, object] = {
                "symbol": normalized_symbol,
                "decision": "NO_TRADE",
                "decision_time": decision_time.isoformat(),
                "reasons": list(analysis.assessment.reasons),
            }
            _emit(payload, f"{normalized_symbol}: NO_TRADE", output_mode)
            return

        signal = signal_from_discovery_setup(setup)
        config = BacktestConfig(maximum_holding_candles=replay_candles)
        trade = simulate_trade(signal, future_candles, config=config)
        report = summarize_trades((trade,))
        payload = {
            "symbol": normalized_symbol,
            "decision_time": decision_time.isoformat(),
            "replay_timeframe": replay_timeframe,
            "replay_candles": len(future_candles),
            "trade": _jsonable(asdict(trade)),
            "metrics": _jsonable(asdict(report) | {"trades": []}),
        }
        text = (
            f"{normalized_symbol}: {trade.outcome.value.upper()} "
            f"| net_pnl={trade.net_pnl:.6f} "
            f"| r={trade.realized_r_multiple:.2f}"
        )
        _emit(payload, text, output_mode)


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
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


__all__ = ["register_backtesting_commands"]
