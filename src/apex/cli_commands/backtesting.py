"""Focused public chronological backtest command."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import httpx
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
from apex.presentation.backtest_output import render_backtest, render_campaign
from apex.presentation.terminal import emit_terminal
from apex.research.campaign import (
    ArchiveSpec,
    CampaignConfig,
    CampaignManifest,
    PublicDataImporter,
    latest_complete_utc_months,
    write_manifest,
)
from apex.research.metrics import (
    deflated_sharpe_probability,
    probability_of_backtest_overfitting,
)
from apex.research.training import train_campaign_models


def register_backtesting_commands(app: typer.Typer) -> None:
    """Register one leak-proof historical strategy-evaluation command."""

    @app.command("backtest")
    def backtest(
        symbol: Annotated[
            str | None,
            typer.Argument(help="Futures symbol; optional with --campaign."),
        ] = None,
        campaign: Annotated[
            bool,
            typer.Option("--campaign", help="Run a point-in-time multi-symbol research campaign."),
        ] = False,
        start: Annotated[str | None, typer.Option("--start", help="UTC month/date start.")] = None,
        end: Annotated[str | None, typer.Option("--end", help="UTC month/date end.")] = None,
        symbols_file: Annotated[
            Path | None,
            typer.Option("--symbols-file", exists=True, dir_okay=False),
        ] = None,
        dataset_dir: Annotated[
            Path,
            typer.Option("--dataset-dir", file_okay=False),
        ] = Path("data/research/binance_um"),
        download_missing: Annotated[bool, typer.Option("--download-missing")] = False,
        train_model: Annotated[bool, typer.Option("--train-model")] = False,
        report_path: Annotated[Path | None, typer.Option("--report")] = None,
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
        ] = "text",
        candle_limit: Annotated[
            int,
            typer.Option("--candles", min=201, max=900),
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

        if campaign:
            payload = _run_public_data_campaign(
                dataset_dir=dataset_dir,
                symbols_file=symbols_file,
                start=start,
                end=end,
                download_missing=download_missing,
                train_model=train_model,
            )
            if report_path is not None:
                report_path.parent.mkdir(parents=True, exist_ok=True)
                report_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            _emit(payload, render_campaign(payload), normalize_cli_output_mode(output))
            return
        if symbol is None:
            raise typer.BadParameter("SYMBOL is required unless --campaign is used")

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
                    futures_evidence_enabled=context.settings.futures_evidence_enabled,
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
        final_returns = tuple(
            trade.realized_r_multiple
            for trade in report.trades
            if partition_by_time.get(trade.signal.generated_at.isoformat()) == "final_test"
        )
        training_value = partition_metrics["training"].get("expectancy", 0.0)
        final_value = partition_metrics["final_test"].get("expectancy", 0.0)
        training_expectancy = (
            float(training_value) if isinstance(training_value, (int, float)) else 0.0
        )
        final_expectancy = float(final_value) if isinstance(final_value, (int, float)) else 0.0
        promotion_statistics = {
            "deflated_sharpe_probability": deflated_sharpe_probability(
                final_returns,
                trials=max(1, len({record.get("strategy") for record in calibration_records})),
            ),
            "probability_backtest_overfitting": probability_of_backtest_overfitting(
                [training_expectancy], [final_expectancy]
            ),
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
            "promotion_statistics": promotion_statistics,
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
        _emit(payload, render_backtest(payload), output_mode)


def _run_public_data_campaign(
    *,
    dataset_dir: Path,
    symbols_file: Path | None,
    start: str | None,
    end: str | None,
    download_missing: bool,
    train_model: bool,
) -> dict[str, Any]:
    months = latest_complete_utc_months(datetime.now(UTC), 24)
    if start is not None:
        months = tuple(month for month in months if month >= start[:7])
    if end is not None:
        months = tuple(month for month in months if month <= end[:7])
    if not months:
        raise typer.BadParameter("campaign date range contains no complete UTC months")
    universe_path = symbols_file or dataset_dir / "universe_by_month.json"
    if not universe_path.exists():
        if not download_missing:
            raise typer.BadParameter(
                "point-in-time universe is absent; use --download-missing to build it "
                "from trailing Binance 1d quote volume"
            )
        with PublicDataImporter(CampaignConfig(dataset_dir=dataset_dir)) as importer:
            universe, universe_missing = importer.build_dynamic_universe(months, limit=30)
        universe_path.parent.mkdir(parents=True, exist_ok=True)
        universe_path.write_text(
            json.dumps({key: list(value) for key, value in universe.items()}, indent=2) + "\n"
        )
    else:
        raw_universe = json.loads(universe_path.read_text())
        universe_missing = {}
        if isinstance(raw_universe, list):
            universe = {
                month: tuple(str(item).upper() for item in raw_universe) for month in months
            }
        elif isinstance(raw_universe, dict):
            universe = {
                month: tuple(str(item).upper() for item in raw_universe.get(month, ()))[:30]
                for month in months
            }
        else:
            raise typer.BadParameter("symbols file must be a JSON list or month-to-symbol mapping")
    files: dict[str, str] = {}
    missing: dict[str, str] = dict(universe_missing)
    if download_missing:
        with PublicDataImporter(CampaignConfig(dataset_dir=dataset_dir)) as importer:
            for month in months:
                for symbol_name in universe[month]:
                    for data_type in ("klines", "fundingRate", "aggTrades"):
                        spec = ArchiveSpec(
                            symbol_name,
                            month,
                            data_type=data_type,
                            timeframe="1m" if data_type == "klines" else None,
                        )
                        try:
                            path, checksum = importer.download(spec)
                            files[str(path.relative_to(dataset_dir))] = checksum
                        except (httpx.HTTPError, OSError, ValueError) as exc:
                            missing[f"{month}:{symbol_name}:{data_type}"] = (
                                f"{type(exc).__name__}: {exc}"
                            )
    manifest = CampaignManifest(
        schema_version=1,
        created_at=datetime.now(UTC).isoformat(),
        complete_months=months,
        universe_by_month=universe,
        files=files,
        missing=missing,
    )
    manifest_path = dataset_dir / "campaign_manifest.json"
    write_manifest(manifest_path, manifest)
    training_result = train_campaign_models(dataset_dir) if train_model else None
    return {
        "schema_version": 1,
        "campaign": True,
        "months": list(months),
        "universe_size": 30,
        "symbol_count": len({symbol for values in universe.values() for symbol in values}),
        "verified_file_count": len(files),
        "missing_file_count": len(missing),
        "manifest": str(manifest_path),
        "manifest_hash": manifest.checksum,
        "train_model_requested": train_model,
        "model_training": training_result if train_model else "not requested",
        "calibration_authoritative": False,
    }


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    emit_terminal(text)


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
        "strategy": serialized.get("strategy"),
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
