"""Explicit simulation and chronological backtest CLI commands."""

from __future__ import annotations

from collections.abc import Mapping
from math import ceil
from pathlib import Path
from typing import Annotated

import typer

from apex.application import (
    BacktestCampaignRequest,
    ChronologicalBacktestRequest,
    MultiSymbolBacktestCampaignRequest,
    bootstrap,
    campaign_result_to_payload,
    create_market_data_services,
    load_default_risk_config,
    normalize_market_symbol,
    parse_campaign_variants,
    run_backtest_campaign,
    run_chronological_pipeline_backtest,
    run_multi_symbol_backtest_campaign,
    split_campaign_candles_by_symbol,
)
from apex.application.backtest_comparison import compare_backtest_reports
from apex.application.backtest_report_io import (
    dumps_report,
    make_run_id,
    to_json_value,
    write_backtest_campaign_sqlite,
    write_backtest_report,
    write_backtest_report_sqlite,
)
from apex.application.chronological_metadata import build_chronological_metadata
from apex.application.futures_risk_mode import futures_risk_mode_scope
from apex.application.historical_dataset import load_historical_candles
from apex.cli import backtest as legacy_simulate_current_setup
from apex.data.providers.errors import MarketDataProviderError
from apex.data.timeframes import timeframe_delta
from apex.domain import Candle, RiskMode
from apex.risk import resolve_risk_config_for_mode


def register_backtesting_commands(app: typer.Typer) -> None:
    @app.command("simulate-current-setup")
    def simulate_current_setup(
        symbol: Annotated[
            str,
            typer.Argument(
                help="One market symbol, or comma-separated symbols for a curated campaign."
            ),
        ],
        output: Annotated[
            str,
            typer.Option("--output", "-o", help="text or json"),
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
        symbol: Annotated[
            str,
            typer.Argument(help="Any provider-supported market symbol."),
        ],
        replay_timeframe: Annotated[
            str,
            typer.Option("--replay-timeframe"),
        ] = "5m",
        history_limit: Annotated[
            int,
            typer.Option("--history-candles", min=80, max=1000),
        ] = 500,
        candle_limit: Annotated[
            int,
            typer.Option("--analysis-candles", min=40, max=500),
        ] = 200,
        decision_interval: Annotated[
            int,
            typer.Option("--decision-interval", min=1),
        ] = 1,
        candidate_cooldown: Annotated[
            int,
            typer.Option("--candidate-cooldown", min=0),
        ] = 3,
        risk_mode: Annotated[
            RiskMode,
            typer.Option(
                "--risk-mode",
                case_sensitive=False,
                help="Strategy approval mode: STANDARD, AGGRESSIVE, or EXTREME.",
            ),
        ] = RiskMode.STANDARD,
        dataset: Annotated[
            Path | None,
            typer.Option(
                "--dataset",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Optional local .json or .csv historical candle dataset.",
            ),
        ] = None,
        report_output: Annotated[
            Path | None,
            typer.Option(
                "--report-output",
                dir_okay=False,
                help="Optional path for the complete JSON backtest report.",
            ),
        ] = None,
        record_db: Annotated[
            Path | None,
            typer.Option(
                "--record-db",
                dir_okay=False,
                help="Optional SQLite database for reproducible backtest reports.",
            ),
        ] = None,
        force: Annotated[
            bool,
            typer.Option("--force", help="Allow replacing report output."),
        ] = False,
    ) -> None:
        canonical = normalize_market_symbol(symbol)
        try:
            context = bootstrap()
            risk_config = resolve_risk_config_for_mode(
                load_default_risk_config(),
                risk_mode,
            )
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            required_timeframes = tuple(dict.fromkeys((*analysis_timeframes, replay_timeframe)))
            candles: Mapping[str, tuple[Candle, ...]]
            if dataset is None:
                history_limits = {
                    timeframe: _aligned_history_limit(
                        timeframe=timeframe,
                        replay_timeframe=replay_timeframe,
                        replay_history_candles=history_limit,
                        analysis_candles=candle_limit,
                    )
                    for timeframe in required_timeframes
                }
                with create_market_data_services(context.settings) as services:
                    candles = {
                        timeframe: tuple(
                            services.candles.fetch_candles(
                                canonical,
                                timeframe,
                                limit=history_limits[timeframe],
                            )
                        )
                        for timeframe in required_timeframes
                    }
                dataset_source = "live-provider"
            else:
                candles = load_historical_candles(
                    dataset,
                    expected_symbol=canonical,
                    required_timeframes=required_timeframes,
                )
                dataset_source = str(dataset)

            request = ChronologicalBacktestRequest(
                symbol=canonical,
                candles_by_timeframe=candles,
                analysis_timeframes=analysis_timeframes,
                replay_timeframe=replay_timeframe,
                candle_limit=candle_limit,
                decision_interval_candles=decision_interval,
                candidate_cooldown_candles=candidate_cooldown,
                risk_config=risk_config,
                strategy_routing=getattr(context.settings, "strategy_routing", None),
                gainer_state_thresholds=getattr(context.settings, "gainer_state_thresholds", None),
            )
            with futures_risk_mode_scope(risk_mode):
                result = run_chronological_pipeline_backtest(request)
            metadata = build_chronological_metadata(
                symbol=canonical,
                candles_by_timeframe=candles,
                analysis_timeframes=request.analysis_timeframes,
                replay_timeframe=replay_timeframe,
                candle_limit=candle_limit,
                decision_interval_candles=decision_interval,
                candidate_cooldown_candles=candidate_cooldown,
                risk_config=risk_config,
                backtest_config=request.backtest_config,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Chronological backtest market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        metadata_payload = to_json_value(metadata)
        metadata_payload["run_id"] = make_run_id(
            symbol=canonical,
            replay_timeframe=replay_timeframe,
            dataset_hash=metadata.dataset_hash,
            config_hash=metadata.config_hash,
        )
        payload = {
            "symbol": canonical,
            "dataset_source": dataset_source,
            "risk_mode": risk_mode.value,
            "metadata": metadata_payload,
            "decision_count": result.decision_count,
            "approved_count": result.approved_count,
            "skipped_count": result.skipped_count,
            "cooldown_skipped_count": result.cooldown_skipped_count,
            "overlap_skipped_count": result.overlap_skipped_count,
            "failure_count": result.failure_count,
            "failures": dict(result.failures),
            "diagnostics": {
                "candidate_count_distribution": dict(result.candidate_count_distribution),
                "rejection_code_counts": dict(result.rejection_code_counts),
                "rejection_reason_counts": dict(result.rejection_reason_counts),
                "skipped_by_stage": dict(result.skipped_by_stage),
                "phase5_outcome_counts": dict(result.phase5_outcome_counts),
                "phase5_reason_counts": dict(result.phase5_reason_counts),
                "phase5_strategy_counts": dict(result.phase5_strategy_counts),
                "phase5_score_bands": dict(result.phase5_score_bands),
                "risk_rejection_diagnostics": [
                    dict(item) for item in result.risk_rejection_diagnostics
                ],
            },
            "metrics": to_json_value(result.report),
            "trades": to_json_value(result.trades),
        }
        if report_output is not None:
            try:
                write_backtest_report(report_output, payload, force=force)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
        if record_db is not None:
            write_backtest_report_sqlite(record_db, payload)
        typer.echo(dumps_report(payload), nl=False)

    @app.command("compare-backtests")
    def compare_backtests(
        left: Annotated[
            Path,
            typer.Argument(exists=True, dir_okay=False, readable=True),
        ],
        right: Annotated[
            Path,
            typer.Argument(exists=True, dir_okay=False, readable=True),
        ],
    ) -> None:
        """Compare identities and aggregate metrics from two saved reports."""
        try:
            comparison = compare_backtest_reports(left, right)
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(dumps_report(comparison), nl=False)

    @app.command("chronological-backtest-campaign")
    def chronological_backtest_campaign(
        symbol: Annotated[
            str,
            typer.Argument(help="Any provider-supported market symbol."),
        ],
        variants: Annotated[
            str | None,
            typer.Option(
                "--variants",
                help=(
                    "Comma-separated id:timeframe:candles:interval:cooldown entries. "
                    "Defaults to baseline, fast-decisions, and slower-decisions."
                ),
            ),
        ] = None,
        history_limit: Annotated[
            int,
            typer.Option("--history-candles", min=80, max=1500),
        ] = 600,
        dataset: Annotated[
            Path | None,
            typer.Option(
                "--dataset",
                exists=True,
                dir_okay=False,
                readable=True,
                help="Optional local .json or .csv historical candle dataset.",
            ),
        ] = None,
        report_output: Annotated[
            Path | None,
            typer.Option(
                "--report-output",
                dir_okay=False,
                help="Optional path for the complete JSON campaign report.",
            ),
        ] = None,
        record_db: Annotated[
            Path | None,
            typer.Option(
                "--record-db",
                dir_okay=False,
                help="Optional SQLite database for reproducible campaign reports.",
            ),
        ] = None,
        force: Annotated[
            bool,
            typer.Option("--force", help="Allow replacing report output."),
        ] = False,
    ) -> None:
        """Run multiple chronological backtest variants without mutating config."""

        try:
            symbols = _parse_campaign_symbols(symbol)
            parsed_variants = parse_campaign_variants(variants)
            context = bootstrap()
            risk_config = load_default_risk_config()
            analysis_timeframes = tuple(context.settings.analysis_timeframes)
            replay_timeframes = tuple(variant.replay_timeframe for variant in parsed_variants)
            required_timeframes = tuple(dict.fromkeys((*analysis_timeframes, *replay_timeframes)))
            candles: Mapping[str, tuple[Candle, ...]]
            candles_by_symbol: Mapping[str, Mapping[str, tuple[Candle, ...]]]
            if dataset is None:
                with create_market_data_services(context.settings) as services:
                    candles_by_symbol = {
                        item: {
                            timeframe: tuple(
                                services.candles.fetch_candles(
                                    item,
                                    timeframe,
                                    limit=history_limit,
                                )
                            )
                            for timeframe in required_timeframes
                        }
                        for item in symbols
                    }
                dataset_source = "live-provider"
            else:
                candles = load_historical_candles(
                    dataset,
                    required_timeframes=required_timeframes,
                )
                candles_by_symbol = split_campaign_candles_by_symbol(candles, symbols)
                dataset_source = str(dataset)
            if len(symbols) == 1:
                result = run_backtest_campaign(
                    BacktestCampaignRequest(
                        symbol=symbols[0],
                        candles_by_timeframe=candles_by_symbol[symbols[0]],
                        analysis_timeframes=analysis_timeframes,
                        variants=parsed_variants,
                        dataset_source=dataset_source,
                        risk_config=risk_config,
                        strategy_routing=getattr(context.settings, "strategy_routing", None),
                        gainer_state_thresholds=getattr(
                            context.settings,
                            "gainer_state_thresholds",
                            None,
                        ),
                    )
                )
            else:
                result = run_multi_symbol_backtest_campaign(
                    MultiSymbolBacktestCampaignRequest(
                        symbols=symbols,
                        candles_by_symbol=candles_by_symbol,
                        analysis_timeframes=analysis_timeframes,
                        variants=parsed_variants,
                        dataset_source=dataset_source,
                        risk_config=risk_config,
                        strategy_routing=getattr(context.settings, "strategy_routing", None),
                        gainer_state_thresholds=getattr(
                            context.settings,
                            "gainer_state_thresholds",
                            None,
                        ),
                    )
                )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        except MarketDataProviderError as exc:
            typer.echo(f"Chronological campaign market-data request failed: {exc}", err=True)
            raise typer.Exit(code=1) from exc

        payload = campaign_result_to_payload(result)
        if report_output is not None:
            try:
                write_backtest_report(report_output, payload, force=force)
            except ValueError as exc:
                raise typer.BadParameter(str(exc)) from exc
        if record_db is not None:
            write_backtest_campaign_sqlite(record_db, payload)
        typer.echo(dumps_report(payload), nl=False)


MAX_LIVE_HISTORY_CANDLES = 10_000


def _aligned_history_limit(
    *,
    timeframe: str,
    replay_timeframe: str,
    replay_history_candles: int,
    analysis_candles: int,
) -> int:
    """Return candles needed for full warmup across the replay horizon."""

    if replay_history_candles < 1:
        raise ValueError("replay history candles must be positive")
    if analysis_candles < 1:
        raise ValueError("analysis candles must be positive")
    if replay_history_candles < analysis_candles:
        raise ValueError("replay history candles must be greater than or equal to analysis candles")

    replay_delta = timeframe_delta(replay_timeframe)
    analysis_delta = timeframe_delta(timeframe)

    replay_span_after_first_decision = (replay_history_candles - analysis_candles) * replay_delta
    required_span = replay_span_after_first_decision + analysis_candles * analysis_delta
    required_candles = max(
        analysis_candles,
        ceil(required_span / analysis_delta),
    )

    if required_candles > MAX_LIVE_HISTORY_CANDLES:
        raise ValueError(
            "aligned live history requires "
            f"{required_candles} candles for {timeframe}, exceeding the "
            f"{MAX_LIVE_HISTORY_CANDLES} candle live-provider limit; "
            "reduce --history-candles or use --dataset"
        )

    return required_candles


def _parse_campaign_symbols(value: str) -> tuple[str, ...]:
    symbols = tuple(
        normalize_market_symbol(item.strip()) for item in value.split(",") if item.strip()
    )
    if not symbols:
        raise ValueError("campaign requires at least one symbol")
    if len(set(symbols)) != len(symbols):
        raise ValueError("campaign symbols must be unique")
    return symbols
