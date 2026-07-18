"""Focused public chronological backtest command."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    analyze_selected_symbol,
    bootstrap,
    create_market_data_services,
    normalize_market_symbol,
    serialize_symbol_analysis,
)
from apex.backtesting.contracts import BacktestConfig, BacktestRequest
from apex.backtesting.discovery_signal import signal_from_discovery_setup
from apex.backtesting.engine import HistoricalBacktestRunner, summarize_trades
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayProvider,
)
from apex.data.providers.errors import MarketDataProviderError
from apex.data.timeframes import timeframe_delta
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
        decision_points: Annotated[
            int,
            typer.Option(
                "--decision-points",
                min=1,
                max=50,
                help="Chronological non-overlapping decisions in the replay campaign.",
            ),
        ] = 5,
        funding_pct: Annotated[
            float,
            typer.Option("--funding-pct", min=0.0, help="Optional modeled funding drag."),
        ] = 0.0,
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
        """Run a chronological multi-decision analysis and replay campaign."""

        try:
            output_mode = normalize_cli_output_mode(output)
            normalized_symbol = normalize_market_symbol(symbol)
            context = bootstrap(config_dir)
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            requested_timeframes = tuple(dict.fromkeys((*analysis_timeframes, replay_timeframe)))
            source_limit = candle_limit + replay_candles * decision_points

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
                                limit=_campaign_source_limit(
                                    timeframe=timeframe,
                                    replay_timeframe=replay_timeframe,
                                    candle_limit=candle_limit,
                                    replay_candles=replay_candles,
                                    decision_points=decision_points,
                                ),
                            )
                            if candle.is_closed
                        ),
                    )
                    for timeframe in requested_timeframes
                )

            replay_series = next(item for item in series if item.timeframe == replay_timeframe)
            if len(replay_series.candles) < source_limit:
                raise ValueError(
                    "backtest requires enough closed candles for analysis and every replay window"
                )
            store = HistoricalCandleStore(series)
            decision_times = tuple(
                replay_series.candles[
                    len(replay_series.candles) - replay_candles * (decision_points - index) - 1
                ].close_time
                for index in range(decision_points)
            )
            signals = []
            no_trade_decisions: list[dict[str, object]] = []
            calibration_records: list[dict[str, object]] = []
            decision_partitions: list[dict[str, str]] = []
            for decision_index, decision_time in enumerate(decision_times):
                partition = _campaign_partition(decision_index, decision_points)
                decision_partitions.append(
                    {"decision_time": decision_time.isoformat(), "partition": partition}
                )
                replay_provider = HistoricalReplayProvider(
                    store=store,
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
                    market_environment_config=context.settings.market_environment,
                )
                setup = analysis.assessment.setup
                calibration_records.append(
                    _calibration_record(
                        analysis=analysis,
                        partition=partition,
                    )
                )
                if setup is None:
                    no_trade_decisions.append(
                        {
                            "decision_time": decision_time.isoformat(),
                            "partition": partition,
                            "reasons": list(analysis.assessment.reasons),
                        }
                    )
                    continue
                signals.append(signal_from_discovery_setup(setup))
        except (StopIteration, ValueError) as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Backtest market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        config = BacktestConfig(
            maximum_holding_candles=replay_candles,
            funding_pct=funding_pct,
        )
        study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=tuple(signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:campaign",
            )
        )
        report = study.report
        replay_outcomes = {
            trade.signal.generated_at.isoformat(): {
                "outcome": trade.outcome.value,
                "realized_r_multiple": trade.realized_r_multiple,
                "net_pnl": trade.net_pnl,
                "maximum_favorable_excursion_r": trade.metadata.get(
                    "maximum_favorable_excursion_r"
                ),
                "maximum_adverse_excursion_r": trade.metadata.get("maximum_adverse_excursion_r"),
            }
            for trade in report.trades
        }
        calibration_records = [
            {
                **record,
                "future_replay": replay_outcomes.get(
                    str(record["decision_time"]),
                    {
                        "outcome": "no_signal",
                        "realized_r_multiple": None,
                        "net_pnl": None,
                        "maximum_favorable_excursion_r": None,
                        "maximum_adverse_excursion_r": None,
                    },
                ),
            }
            for record in calibration_records
        ]
        partition_by_time = {
            item["decision_time"]: item["partition"] for item in decision_partitions
        }
        partition_metrics = {
            partition: _report_metrics(
                summarize_trades(
                    tuple(
                        trade
                        for trade in report.trades
                        if partition_by_time.get(trade.signal.generated_at.isoformat()) == partition
                    )
                )
            )
            for partition in ("training", "validation", "final_test")
        }
        payload = {
            "schema_version": 2,
            "symbol": normalized_symbol,
            "replay_timeframe": replay_timeframe,
            "replay_candles": replay_candles,
            "decision_point_count": decision_points,
            "generated_signal_count": study.generated_signal_count,
            "no_trade_decision_count": len(no_trade_decisions),
            "decision_times": [item.isoformat() for item in decision_times],
            "decision_partitions": decision_partitions,
            "no_trade_decisions": no_trade_decisions,
            "calibration_records": calibration_records,
            "trades": [_jsonable(trade) for trade in report.trades],
            "metrics": _report_metrics(report),
            "metrics_by_partition": partition_metrics,
            "calibration_authoritative": False,
            "study": {
                "dataset_hash": study.dataset_hash,
                "config_hash": study.config_hash,
                "code_hash": study.code_hash,
                "skipped_signal_count": study.skipped_signal_count,
            },
        }
        if len(report.trades) == 1:
            payload["trade"] = _jsonable(report.trades[0])
        text = (
            f"{normalized_symbol}: CAMPAIGN | decisions={decision_points} "
            f"| signals={study.generated_signal_count} | trades={report.total_trades} "
            f"| expectancy={report.expectancy:.6f} | net_pnl={report.net_profit:.6f}"
        )
        _emit(payload, text, output_mode)


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    typer.echo(text)


def _campaign_partition(index: int, total: int) -> str:
    """Assign frozen chronological evaluation partitions without shuffling."""

    if total <= 1:
        return "final_test"
    training_end = min(max(1, int(total * 0.6)), total - 1)
    validation_end = min(max(training_end + 1, int(total * 0.8)), total - 1)
    if index < training_end:
        return "training"
    if index < validation_end:
        return "validation"
    return "final_test"


def _campaign_source_limit(
    *,
    timeframe: str,
    replay_timeframe: str,
    candle_limit: int,
    replay_candles: int,
    decision_points: int,
) -> int:
    """Retain a full analysis prefix at the earliest replay decision."""

    horizon = timeframe_delta(replay_timeframe) * replay_candles * decision_points
    displaced_bars = math.ceil(horizon / timeframe_delta(timeframe))
    # Cover the active provider candle, interval-boundary alignment, and the
    # analysis core's closed-prefix/provisional-candle lookback.
    return candle_limit + displaced_bars + 4


def _calibration_record(*, analysis: object, partition: str) -> dict[str, object]:
    serialized = serialize_symbol_analysis(analysis)  # type: ignore[arg-type]
    setup = serialized.get("setup")
    diagnostics = serialized.get("phase5_diagnostics")
    zero_trade = (
        diagnostics.get("zero_trade_diagnostics") if isinstance(diagnostics, Mapping) else None
    )
    methodology_routing = (
        diagnostics.get("methodology_candidate_routing")
        if isinstance(diagnostics, Mapping)
        else None
    )
    return {
        "schema_version": 1,
        "symbol": serialized.get("symbol"),
        "decision_time": serialized.get("generated_at"),
        "partition": partition,
        "production_decision": serialized.get("decision"),
        "methodology_gate_mode": (
            methodology_routing.get("mode") if isinstance(methodology_routing, Mapping) else None
        ),
        "methodology_decision": (
            {
                "suppressed_candidate_count": methodology_routing.get("suppressed_candidate_count"),
                "suppressed_strategies": methodology_routing.get("suppressed_strategies"),
                "reason_codes": methodology_routing.get("reason_codes"),
            }
            if isinstance(methodology_routing, Mapping)
            else None
        ),
        "no_trade_reasons": serialized.get("reasons"),
        "zero_trade_diagnostics": zero_trade,
        "entry_geometry": None if not isinstance(setup, Mapping) else setup.get("entry"),
        "stop_geometry": None if not isinstance(setup, Mapping) else setup.get("stop_loss"),
        "target_geometry": None if not isinstance(setup, Mapping) else setup.get("take_profits"),
    }


def _jsonable(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return {field.name: _jsonable(getattr(value, field.name)) for field in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    if hasattr(value, "value"):
        return value.value
    return value


def _report_metrics(report: object) -> dict[str, object]:
    payload = _jsonable(report)
    if not isinstance(payload, dict):
        raise TypeError("backtest report must serialize to an object")
    payload["trades"] = []
    return payload


__all__ = ["register_backtesting_commands"]
