"""Focused public chronological backtest command."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import fields, is_dataclass
from datetime import UTC, datetime
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
from apex.application.candidate_metadata_shadow import shadow_metadata_from_mapping
from apex.application.candidate_ranking import CandidateRankingRecord, CandidateRankingSnapshot
from apex.application.canonical_opportunity_selection import (
    CanonicalOpportunityDecision,
    select_canonical_opportunity_decision,
    select_replay_opportunity_decisions,
)
from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_geometry_runtime import (
    geometry_execution_costs_from_settings,
)
from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestRequest,
    BacktestSignal,
    SimulatedTrade,
)
from apex.backtesting.discovery_signal import signal_from_discovery_setup
from apex.backtesting.engine import HistoricalBacktestRunner, summarize_trades
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayProvider,
)
from apex.backtesting.methodology_segmentation import methodology_segment_metrics
from apex.data.providers.errors import MarketDataProviderError
from apex.data.timeframes import timeframe_delta
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.backtest_output import render_backtest
from apex.presentation.terminal import emit_terminal
from apex.research.metrics import (
    deflated_sharpe_probability,
    probability_of_backtest_overfitting,
)
from apex.strategies import StrategyType, TradeDirection

_ReplayDecision = CanonicalOpportunityDecision
_select_replay_decision = select_canonical_opportunity_decision


def register_backtesting_commands(app: typer.Typer) -> None:
    """Register one leak-proof historical strategy-evaluation command."""

    @app.command("backtest")
    def backtest(
        symbol: Annotated[
            str,
            typer.Argument(help="Futures symbol to replay chronologically."),
        ],
        report_file: Annotated[
            Path | None,
            typer.Option(
                "--report-file",
                help="Write the complete structured backtest payload to this JSON file.",
            ),
        ] = None,
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
        as_of: Annotated[
            str | None,
            typer.Option(
                "--as-of",
                help=(
                    "Anchor the latest visible candle to an ISO-8601 timestamp "
                    "for repeatable cross-profile campaigns."
                ),
            ),
        ] = None,
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
            anchor_time = _parse_as_of(as_of)
            fetch_time = datetime.now(UTC)
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
                                limit=min(
                                    10_000,
                                    _campaign_source_limit(
                                        timeframe=timeframe,
                                        replay_timeframe=replay_timeframe,
                                        candle_limit=candle_limit,
                                        replay_candles=replay_candles,
                                        decision_points=decision_points,
                                    )
                                    + _anchor_displaced_bars(
                                        timeframe=timeframe,
                                        anchor_time=anchor_time,
                                        fetch_time=fetch_time,
                                    ),
                                ),
                            )
                            if candle.is_closed
                            and (anchor_time is None or candle.close_time <= anchor_time)
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
            signals: list[BacktestSignal] = []
            conditional_signals: list[BacktestSignal] = []
            opportunity_signals: list[BacktestSignal] = []
            shadow_signals: list[BacktestSignal] = []
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
                    timeframe_indicator_profiles=getattr(
                        context.settings, "timeframe_indicator_profiles", None
                    ),
                    candle_limit=candle_limit,
                    generated_at=decision_time,
                    strategy_routing=getattr(context.settings, "strategy_routing", None),
                    market_environment_config=context.settings.market_environment,
                    methodology_gate_mode=context.settings.methodology_gate_mode,
                    methodology_settings=context.settings.methodology,
                    geometry_safety_mode=(
                        context.settings.methodology_gate_mode
                        if context.settings.geometry_execution.enabled
                        else "shadow"
                    ),
                    geometry_execution_costs=geometry_execution_costs_from_settings(
                        context.settings.geometry_execution
                    ),
                    futures_evidence_enabled=context.settings.futures_evidence_enabled,
                )
                replay_decision = _select_replay_decision(analysis)
                shadow_signals.extend(_shadow_replay_signals(analysis))
                for opportunity_decision in select_replay_opportunity_decisions(analysis):
                    opportunity_setup = opportunity_decision.setup
                    if opportunity_setup is None:
                        continue
                    opportunity_signals.append(
                        signal_from_discovery_setup(
                            opportunity_setup,
                            replay_timeframe=replay_timeframe,
                            replay_source="opportunity_portfolio",
                        )
                    )
                setup = replay_decision.setup
                calibration_records.append(
                    _calibration_record(
                        analysis=analysis,
                        partition=partition,
                        replay_decision=replay_decision,
                    )
                )
                if setup is None or not replay_decision.execution_authorized:
                    no_trade_decisions.append(
                        {
                            "decision_time": decision_time.isoformat(),
                            "partition": partition,
                            "reasons": [
                                replay_decision.reason_code,
                                *analysis.assessment.reasons,
                            ],
                            "canonical_portfolio": replay_decision.canonical_portfolio,
                        }
                    )
                    if setup is not None and setup.conditional_plan is not None:
                        conditional_signals.append(
                            signal_from_discovery_setup(
                                setup,
                                replay_timeframe=replay_timeframe,
                                replay_source="conditional_portfolio",
                            )
                        )
                    continue
                signals.append(
                    signal_from_discovery_setup(
                        setup,
                        replay_timeframe=replay_timeframe,
                    )
                )
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
        conditional_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=tuple(conditional_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:conditional-campaign",
            )
        )
        opportunity_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=tuple(opportunity_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:opportunity-campaign",
            )
        )
        shadow_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=tuple(shadow_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:shadow-campaign",
            )
        )
        report = study.report
        conditional_report = conditional_study.report
        opportunity_report = opportunity_study.report
        shadow_report = shadow_study.report

        def replay_record(trade: SimulatedTrade, replay_class: str) -> dict[str, object]:
            metadata = getattr(trade, "metadata", {})
            return {
                "outcome": trade.outcome.value,
                "realized_r_multiple": trade.realized_r_multiple,
                "net_pnl": trade.net_pnl,
                "maximum_favorable_excursion_r": metadata.get("maximum_favorable_excursion_r"),
                "maximum_adverse_excursion_r": metadata.get("maximum_adverse_excursion_r"),
                "activation_outcome": metadata.get("activation_outcome"),
                "replay_class": replay_class,
            }

        replay_outcomes = {
            trade.signal.generated_at.isoformat(): replay_record(trade, "production")
            for trade in report.trades
        }
        replay_outcomes.update(
            {
                trade.signal.generated_at.isoformat(): replay_record(trade, "conditional")
                for trade in conditional_report.trades
            }
        )
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
                        "activation_outcome": None,
                        "replay_class": "none",
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
            "deflated_sharpe_probability": (
                deflated_sharpe_probability(
                    final_returns,
                    trials=max(
                        1,
                        len({record.get("strategy") for record in calibration_records}),
                    ),
                )
                if final_returns
                else None
            ),
            "probability_backtest_overfitting": (
                probability_of_backtest_overfitting(
                    [training_expectancy],
                    [final_expectancy],
                )
                if report.total_trades > 0
                else None
            ),
        }
        decision_funnel = _decision_funnel_metrics(
            decision_point_count=decision_points,
            production_signals=study.generated_signal_count,
            conditional_signals=conditional_study.generated_signal_count,
            no_trade_decisions=no_trade_decisions,
            production_trades=report.trades,
            conditional_trades=conditional_report.trades,
        )
        payload = {
            "schema_version": 5,
            "symbol": normalized_symbol,
            "replay_timeframe": replay_timeframe,
            "replay_candles": replay_candles,
            "decision_point_count": decision_points,
            "as_of": None if anchor_time is None else anchor_time.isoformat(),
            "generated_signal_count": study.generated_signal_count,
            "no_trade_decision_count": len(no_trade_decisions),
            "decision_times": [item.isoformat() for item in decision_times],
            "decision_partitions": decision_partitions,
            "no_trade_decisions": no_trade_decisions,
            "calibration_records": calibration_records,
            "methodology_segment_metrics": methodology_segment_metrics(calibration_records),
            "trades": _canonical_trade_records(
                report.trades,
                calibration_records=calibration_records,
                partition_by_time=partition_by_time,
                fee_pct=config.fee_pct,
                slippage_pct=config.slippage_pct,
            ),
            "metrics": _report_metrics(report),
            "execution_metrics": _execution_metrics(report.trades),
            "decision_funnel": decision_funnel,
            "outcome_distribution": _outcome_distribution(report.trades),
            "risk_and_excursion": _risk_and_excursion(report.trades),
            "execution_assumptions": {
                "fee_pct": config.fee_pct,
                "slippage_pct": config.slippage_pct,
                "funding_pct": config.funding_pct,
                "maximum_holding_candles": config.maximum_holding_candles,
                "conservative_intrabar": config.conservative_intrabar,
                "methodology_gate_mode": context.settings.methodology_gate_mode,
            },
            "metrics_by_partition": partition_metrics,
            "promotion_statistics": promotion_statistics,
            "calibration_authoritative": False,
            "conditional_replay": {
                "signal_count": conditional_study.generated_signal_count,
                "trades": _canonical_trade_records(
                    conditional_report.trades,
                    calibration_records=calibration_records,
                    partition_by_time=partition_by_time,
                    fee_pct=config.fee_pct,
                    slippage_pct=config.slippage_pct,
                ),
                "metrics": _report_metrics(conditional_report),
                "activation_metrics": _activation_metrics(conditional_report.trades),
                "execution_metrics": _execution_metrics(conditional_report.trades),
                "outcome_distribution": _outcome_distribution(conditional_report.trades),
                "risk_and_excursion": _risk_and_excursion(conditional_report.trades),
                "calibration_authoritative": False,
            },
            "opportunity_replay": {
                "signal_count": opportunity_study.generated_signal_count,
                "simulated_trade_count": opportunity_study.simulated_trade_count,
                "skipped_signal_count": opportunity_study.skipped_signal_count,
                "trades": _canonical_trade_records(
                    opportunity_report.trades,
                    calibration_records=calibration_records,
                    partition_by_time=partition_by_time,
                    fee_pct=config.fee_pct,
                    slippage_pct=config.slippage_pct,
                ),
                "metrics": _diagnostic_report_metrics(opportunity_report),
                "activation_metrics": _activation_metrics(opportunity_report.trades),
                "execution_metrics": _execution_metrics(opportunity_report.trades),
                "outcome_distribution": _outcome_distribution(opportunity_report.trades),
                "risk_and_excursion": _risk_and_excursion(opportunity_report.trades),
                "calibration_authoritative": False,
                "portfolio_drawdown_valid": False,
                "purpose": (
                    "diagnostic replay of every distinct retained executable or "
                    "conditional portfolio opportunity; canonical production metrics "
                    "remain authoritative"
                ),
            },
            "shadow_replay": {
                "signal_count": shadow_study.generated_signal_count,
                "trades": _canonical_trade_records(
                    shadow_report.trades,
                    calibration_records=calibration_records,
                    partition_by_time=partition_by_time,
                    fee_pct=config.fee_pct,
                    slippage_pct=config.slippage_pct,
                ),
                "metrics": _diagnostic_report_metrics(shadow_report),
                "outcome_distribution": _outcome_distribution(shadow_report.trades),
                "risk_and_excursion": _risk_and_excursion(shadow_report.trades),
                "source_distribution": _shadow_source_distribution(shadow_report.trades),
                "direction_accuracy": _direction_accuracy(shadow_report.trades),
                "calibration_authoritative": False,
                "portfolio_drawdown_valid": False,
            },
            "study": {
                "dataset_hash": study.dataset_hash,
                "config_hash": study.config_hash,
                "code_hash": study.code_hash,
                "skipped_signal_count": study.skipped_signal_count,
            },
        }
        if len(report.trades) == 1:
            payload["trade"] = _jsonable(report.trades[0])
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
            )
        _emit(payload, render_backtest(payload), output_mode)


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


def _parse_as_of(value: str | None) -> datetime | None:
    if value is None:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    if not normalized:
        raise ValueError("as-of timestamp cannot be blank")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError("as-of must be a valid ISO-8601 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("as-of timestamp must include a timezone")
    anchored = parsed.astimezone(UTC)
    if anchored > datetime.now(UTC):
        raise ValueError("as-of timestamp cannot be in the future")
    return anchored


def _anchor_displaced_bars(
    *,
    timeframe: str,
    anchor_time: datetime | None,
    fetch_time: datetime,
) -> int:
    if anchor_time is None or anchor_time >= fetch_time:
        return 0
    return math.ceil((fetch_time - anchor_time) / timeframe_delta(timeframe)) + 2


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


def _calibration_record(
    *,
    analysis: object,
    partition: str,
    replay_decision: _ReplayDecision | None = None,
) -> dict[str, object]:
    resolved_decision = (
        _select_replay_decision(analysis) if replay_decision is None else replay_decision
    )
    serialized = serialize_symbol_analysis(analysis)  # type: ignore[arg-type]
    setup = resolved_decision.setup
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
        "schema_version": 2,
        "symbol": serialized.get("symbol"),
        "decision_time": serialized.get("generated_at"),
        "partition": partition,
        "production_decision": serialized.get("decision"),
        "strategy": None if setup is None else setup.strategy.value,
        "direction": None if setup is None else setup.direction.value,
        "opportunity_id": resolved_decision.opportunity_id,
        "sequence_role": resolved_decision.sequence_role,
        "lane": resolved_decision.lane,
        "actionability_state": resolved_decision.actionability_state,
        "replay_reason_code": resolved_decision.reason_code,
        "canonical_portfolio": resolved_decision.canonical_portfolio,
        "execution_authorized": resolved_decision.execution_authorized,
        "replay_class": (
            "production"
            if resolved_decision.execution_authorized
            else "conditional"
            if setup is not None and setup.conditional_plan is not None
            else "none"
        ),
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
        "lane_horizon_audits": (
            methodology_routing.get("lane_horizon_audits")
            if isinstance(methodology_routing, Mapping)
            else None
        ),
        "methodology_version": serialized.get("methodology_version"),
        "no_trade_reasons": serialized.get("reasons"),
        "zero_trade_diagnostics": zero_trade,
        "layered_state": None if setup is None else setup.layered_state.to_dict(),
        "score_components": None if setup is None else setup.methodology_scores.to_dict(),
        "continuation_state": (
            None if setup is None else setup.layered_state.continuation_state.value
        ),
        "runner_qualified": None if setup is None else setup.runner_qualified,
        "runner_qualification_reason": (
            None if setup is None else setup.runner_qualification_reason
        ),
        "entry_geometry": None if setup is None else _jsonable(setup.entry),
        "stop_geometry": None if setup is None else _jsonable(setup.stop_loss),
        "target_geometry": None if setup is None else _jsonable(setup.take_profits),
        "target_basis": (
            None if setup is None else [target.target_basis for target in setup.take_profits]
        ),
        "candidate_diagnostics": _candidate_diagnostics(analysis),
        "confirmation_diagnostics": _decision_confirmation_diagnostics(
            analysis=analysis,
            setup=setup,
        ),
        "rejection_reason": (resolved_decision.reason_code if setup is None else None),
    }


def _shadow_replay_signals(analysis: object) -> tuple[BacktestSignal, ...]:
    """Build diagnostic-only signals without changing the production decision."""

    signals: list[BacktestSignal] = []
    ranking = getattr(analysis, "candidate_ranking", None)
    if isinstance(ranking, CandidateRankingSnapshot):
        records = (
            (() if ranking.primary is None else (ranking.primary,))
            + ranking.alternatives
            + ranking.rejected
        )
        for record in records:
            signal = _signal_from_ranking_record(analysis, record)
            if signal is not None:
                signals.append(signal)

    diagnostics = getattr(analysis, "phase5_diagnostics", None)
    routing = (
        diagnostics.get("methodology_candidate_routing")
        if isinstance(diagnostics, Mapping)
        else None
    )
    audits = routing.get("geometry_safety_audits") if isinstance(routing, Mapping) else None
    if isinstance(audits, list | tuple):
        for audit in audits:
            signal = _signal_from_geometry_audit(analysis, audit)
            if signal is not None:
                signals.append(signal)

    portfolio = getattr(analysis, "opportunity_portfolio", None)
    runner_plan = getattr(portfolio, "runner_plan", None)
    runner_setup = getattr(runner_plan, "setup", None)
    if isinstance(runner_setup, DiscoverySetup):
        signals.append(
            signal_from_discovery_setup(
                runner_setup,
                replay_source="runner_plan",
            )
        )

    unique: list[BacktestSignal] = []
    seen: set[tuple[object, ...]] = set()
    for signal in signals:
        # Strategy aliases often emit the exact same trade.  Shadow evidence is
        # calibrated per unique time/direction/geometry, not per label.
        key = (
            signal.generated_at,
            signal.direction,
            "runner" if signal.replay_source == "runner_plan" else "entry",
            round(signal.entry_price, 10),
            round(signal.stop_price, 10),
            round(signal.target_price, 10),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(signal)
    return tuple(unique)


def _signal_from_ranking_record(
    analysis: object,
    record: CandidateRankingRecord,
) -> BacktestSignal | None:
    entry = _mapping_value(record.entry, "preferred")
    metadata_stop = _mapping_value(record.metadata, "executable_stop")
    stop = metadata_stop or _mapping_value(record.invalidation, "price")
    targets = tuple(
        price for target in record.targets if (price := _mapping_value(target, "price")) is not None
    )
    if entry is None or stop is None or not targets:
        return None
    source = {
        "primary": "retained_primary",
        "alternative": "retained_alternative",
        "rejected": "score_or_collision_rejected",
    }[record.role.value]
    return _build_shadow_signal(
        symbol=str(getattr(analysis, "symbol", "")),
        decision_time=getattr(analysis, "generated_at", None),
        candidate_id=record.candidate_id,
        strategy=record.strategy,
        direction=record.direction,
        entry=entry,
        stop=stop,
        target=targets[0],
        confidence=record.final_score,
        source=source,
        diagnostics=_ranking_diagnostics(record, entry=entry, stop=stop, target=targets[0]),
    )


def _signal_from_geometry_audit(analysis: object, audit: object) -> BacktestSignal | None:
    if not isinstance(audit, Mapping) or audit.get("state") != "reject":
        return None
    item = audit.get("diagnostics")
    candidate_id = audit.get("candidate_id")
    if not isinstance(item, Mapping) or not isinstance(candidate_id, str):
        return None
    identity = candidate_id.split(":")
    if len(identity) < 2:
        return None
    return _build_shadow_signal(
        symbol=str(getattr(analysis, "symbol", "")),
        decision_time=getattr(analysis, "generated_at", None),
        candidate_id=candidate_id,
        strategy=identity[0],
        direction=identity[1],
        entry=_mapping_value(item, "selected_entry"),
        stop=_mapping_value(item, "executable_stop"),
        target=_mapping_value(item, "tp1_price"),
        confidence=0.0,
        source="geometry_rejected",
        diagnostics=_geometry_audit_diagnostics(item),
    )


def _build_shadow_signal(
    *,
    symbol: str,
    decision_time: object,
    candidate_id: str,
    strategy: str,
    direction: str,
    entry: float | None,
    stop: float | None,
    target: float | None,
    confidence: float,
    source: str,
    diagnostics: Mapping[str, object] | None = None,
) -> BacktestSignal | None:
    if not symbol.strip() or not hasattr(decision_time, "utcoffset"):
        return None
    if entry is None or stop is None or target is None:
        return None
    try:
        return BacktestSignal(
            symbol=symbol,
            strategy=StrategyType(strategy),
            direction=TradeDirection(direction),
            generated_at=decision_time,  # type: ignore[arg-type]
            entry_price=entry,
            stop_price=stop,
            target_price=target,
            quantity=1.0,
            risk_amount=abs(entry - stop),
            confidence_score=max(0.0, min(100.0, confidence)),
            candidate_id=candidate_id,
            replay_source=source,
            diagnostics={} if diagnostics is None else diagnostics,
        )
    except (TypeError, ValueError):
        return None


_CONFIRMATION_KEYS = (
    "entry_confirmation_complete",
    "recent_continuation_break",
    "setup_direction_confirmed",
    "immediate_timeframe_conflict",
    "lower_timeframe_trigger_confirmed",
    "lower_timeframe_trigger_opposed",
    "higher_timeframe_conflict",
    "continuation_requires_conditional_entry",
    "continuation_freshness",
    "continuation_state",
    "participation_state",
    "provisional",
    "provisional_state",
    "confirmation_reason",
)

_DIAGNOSTIC_ALIASES: Mapping[str, tuple[str, ...]] = {
    "continuation_freshness": ("continuation_freshness", "freshness", "setup_freshness"),
    "participation_state": ("participation_state", "participation", "volume_participation"),
    "provisional_state": ("provisional_state", "provisional"),
    "confirmation_reason": (
        "confirmation_reason",
        "confirmation_rationale",
        "entry_confirmation_reason",
    ),
}


def _recursive_lookup(value: object, keys: tuple[str, ...]) -> object | None:
    if isinstance(value, Mapping):
        for key in keys:
            if key in value and value[key] is not None:
                return _jsonable(value[key])
        for nested in value.values():
            found = _recursive_lookup(nested, keys)
            if found is not None:
                return found
    elif isinstance(value, (list, tuple)):
        for nested in value:
            found = _recursive_lookup(nested, keys)
            if found is not None:
                return found
    return None


def _confirmation_diagnostics(value: object) -> dict[str, object | None]:
    return {
        key: _recursive_lookup(value, _DIAGNOSTIC_ALIASES.get(key, (key,)))
        for key in _CONFIRMATION_KEYS
    }


def _ranking_diagnostics(
    record: CandidateRankingRecord, *, entry: float, stop: float, target: float
) -> dict[str, object]:
    risk = abs(entry - stop)
    target_payload = record.targets[0] if record.targets else {}
    shadow_metadata = shadow_metadata_from_mapping(
        record.metadata,
        entry_horizon=record.entry.get("horizon"),
    )
    combined = {
        "metadata": shadow_metadata,
        "evidence": dict(record.evidence),
        "methodology_state": dict(record.methodology_state),
        "methodology_scores": dict(record.methodology_scores),
    }
    dimensions = _jsonable(record.score_dimensions)
    return {
        "diagnostic_schema_version": 1,
        "candidate_id": record.candidate_id,
        "ranking_role": record.role.value,
        "strategy": record.strategy,
        "strategy_family": record.strategy_family,
        "strategy_subtype": record.strategy_subtype,
        "direction": record.direction,
        "entry_status": record.entry_status.value,
        "entry_mode": record.entry.get("mode"),
        "final_score": record.final_score,
        "final_rank_score": record.final_rank_score,
        "score_dimensions": dimensions if isinstance(dimensions, dict) else {},
        "methodology_scores": dict(record.methodology_scores),
        "target_quality": _recursive_lookup(
            combined, ("target_quality", "reward_quality", "target_quality_score")
        ),
        "net_tp1_r": _recursive_lookup(
            {"target": target_payload, **combined}, ("net_risk_reward", "net_tp1_r", "net_rr")
        ),
        "gross_tp1_r": abs(target - entry) / risk if risk > 0.0 else None,
        "entry_atr_distance": record.entry.get("atr_distance"),
        "entry_distance_from_current": record.entry.get("distance_from_current"),
        "stop_distance": risk,
        "stop_distance_pct": (risk / entry) * 100.0 if entry > 0.0 else None,
        "stop_distance_atr": _recursive_lookup(
            combined, ("stop_distance_atr", "stop_atr_distance", "risk_atr")
        ),
        "higher_timeframe_relationship": _recursive_lookup(
            combined, ("timeframe_relationship", "higher_timeframe_relationship")
        ),
        "higher_timeframe_severity": _recursive_lookup(
            combined, ("relationship_severity", "higher_timeframe_severity", "htf_severity")
        ),
        "freshness": _recursive_lookup(
            combined, ("freshness", "continuation_freshness", "setup_freshness")
        ),
        "participation": _recursive_lookup(
            combined, ("participation_state", "participation", "volume_participation")
        ),
        "momentum_alignment": _recursive_lookup(
            combined, ("momentum_alignment", "directional_alignment")
        ),
        "provisional": record.provisional,
        "confirmation": _confirmation_diagnostics(combined),
        "ranking_outcome": record.outcome,
        "reason_codes": list(record.reason_codes),
        "execution_timeframe": shadow_metadata.get("execution_timeframe"),
        "setup_timeframe": shadow_metadata.get("setup_timeframe"),
        "invalidation_timeframe": shadow_metadata.get("invalidation_timeframe"),
        "target_timeframe": shadow_metadata.get("target_timeframe"),
        "expected_bars_to_target": shadow_metadata.get("expected_bars_to_target"),
        "decision_atr": shadow_metadata.get("decision_atr"),
        "lifecycle_model": shadow_metadata.get("lifecycle_model"),
        "legacy_context_lane": shadow_metadata.get("legacy_context_lane"),
        "measured_context_lane": shadow_metadata.get("measured_context_lane"),
        "legacy_holding_horizon": shadow_metadata.get("legacy_holding_horizon"),
        "measured_holding_horizon": shadow_metadata.get("measured_holding_horizon"),
        "would_change_lane": shadow_metadata.get("would_change_lane"),
        "would_change_geometry_result": shadow_metadata.get("would_change_geometry_result"),
    }


def _geometry_audit_diagnostics(audit: Mapping[str, object]) -> dict[str, object]:
    diagnostics = audit.get("diagnostics")
    diagnostic_values = diagnostics if isinstance(diagnostics, Mapping) else {}
    candidate_id = audit.get("candidate_id")
    strategy = (
        candidate_id.split(":", maxsplit=1)[0]
        if isinstance(candidate_id, str) and ":" in candidate_id
        else None
    )
    raw_geometry = diagnostic_values.get("geometry_audit")
    geometry_values = raw_geometry if isinstance(raw_geometry, Mapping) else diagnostic_values
    shadow_source = dict(geometry_values)
    legacy_lane = (
        audit.get("lane")
        or audit.get("context_lane")
        or diagnostic_values.get("geometry_lane")
        or diagnostic_values.get("context_lane")
    )
    if isinstance(legacy_lane, str):
        shadow_source.setdefault("context_lane", legacy_lane)
    shadow_metadata = shadow_metadata_from_mapping(
        shadow_source,
        strategy=strategy,
        entry_price=geometry_values.get("selected_entry"),
        target_price=geometry_values.get("tp1_price"),
    )
    state = audit.get("state")
    missing = audit.get("missing_measurements")
    rejection_codes = audit.get("rejection_codes")
    reasons = audit.get("reasons")

    return {
        "diagnostic_schema_version": 2,
        "geometry_audit": _jsonable(diagnostic_values),
        "geometry_available": bool(audit.get("available")),
        "geometry_complete": bool(audit.get("available")) and not bool(missing),
        "geometry_state": state,
        "geometry_passed": state == "pass",
        "geometry_lane": audit.get("lane"),
        "geometry_rejection_codes": (
            list(rejection_codes) if isinstance(rejection_codes, (list, tuple)) else []
        ),
        "geometry_reasons": list(reasons) if isinstance(reasons, (list, tuple)) else [],
        "geometry_missing_measurements": (
            list(missing) if isinstance(missing, (list, tuple)) else []
        ),
        "confirmation": _confirmation_diagnostics(diagnostic_values),
        "execution_timeframe": shadow_metadata.get("execution_timeframe"),
        "setup_timeframe": shadow_metadata.get("setup_timeframe"),
        "invalidation_timeframe": shadow_metadata.get("invalidation_timeframe"),
        "target_timeframe": shadow_metadata.get("target_timeframe"),
        "expected_bars_to_target": shadow_metadata.get("expected_bars_to_target"),
        "decision_atr": shadow_metadata.get("decision_atr"),
        "lifecycle_model": shadow_metadata.get("lifecycle_model"),
        "legacy_context_lane": shadow_metadata.get("legacy_context_lane"),
        "measured_context_lane": shadow_metadata.get("measured_context_lane"),
        "legacy_holding_horizon": shadow_metadata.get("legacy_holding_horizon"),
        "measured_holding_horizon": shadow_metadata.get("measured_holding_horizon"),
        "would_change_lane": shadow_metadata.get("would_change_lane"),
        "legacy_geometry_passed": audit.get("legacy_geometry_passed"),
        "measured_geometry_lane": audit.get("measured_geometry_lane"),
        "measured_geometry_passed": audit.get("measured_geometry_passed"),
        "would_change_geometry_result": audit.get("would_change_geometry_result"),
        "legacy_geometry_rejection_codes": audit.get("legacy_geometry_rejection_codes", []),
        "measured_geometry_rejection_codes": audit.get("measured_geometry_rejection_codes", []),
        "legacy_maximum_tp1_distance_atr": audit.get("legacy_maximum_tp1_distance_atr"),
        "measured_maximum_tp1_distance_atr": audit.get("measured_maximum_tp1_distance_atr"),
        "measured_geometry_reasons": audit.get("measured_geometry_reasons", []),
        "measured_lane_basis": audit.get("measured_lane_basis"),
    }


def _candidate_diagnostics(analysis: object) -> list[dict[str, object]]:
    """Preserve candidate evidence even when no canonical setup survives."""

    diagnostics: list[dict[str, object]] = []
    ranking = getattr(analysis, "candidate_ranking", None)
    if isinstance(ranking, CandidateRankingSnapshot):
        records = (
            (() if ranking.primary is None else (ranking.primary,))
            + ranking.alternatives
            + ranking.rejected
        )
        for record in records:
            entry = _mapping_value(record.entry, "preferred")
            stop = _mapping_value(record.metadata, "executable_stop") or _mapping_value(
                record.invalidation, "price"
            )
            targets = tuple(
                price
                for target in record.targets
                if (price := _mapping_value(target, "price")) is not None
            )
            if entry is None or stop is None or not targets:
                diagnostics.append(
                    {
                        "diagnostic_schema_version": 1,
                        "candidate_id": record.candidate_id,
                        "ranking_role": record.role.value,
                        "strategy": record.strategy,
                        "direction": record.direction,
                        "entry_status": record.entry_status.value,
                        "final_score": record.final_score,
                        "final_rank_score": record.final_rank_score,
                        "confirmation": _confirmation_diagnostics(
                            {
                                "metadata": dict(record.metadata),
                                "evidence": dict(record.evidence),
                                "methodology_state": dict(record.methodology_state),
                                "methodology_scores": dict(record.methodology_scores),
                            }
                        ),
                        "geometry_complete": False,
                    }
                )
                continue
            item = _ranking_diagnostics(
                record,
                entry=entry,
                stop=stop,
                target=targets[0],
            )
            item["geometry_complete"] = True
            diagnostics.append(item)

    phase5 = getattr(analysis, "phase5_diagnostics", None)
    routing = phase5.get("methodology_candidate_routing") if isinstance(phase5, Mapping) else None
    audits = routing.get("geometry_safety_audits") if isinstance(routing, Mapping) else None
    if isinstance(audits, (list, tuple)):
        for audit in audits:
            if not isinstance(audit, Mapping) or audit.get("state") != "reject":
                continue
            audit_diagnostics = audit.get("diagnostics")
            if not isinstance(audit_diagnostics, Mapping):
                continue
            item = _geometry_audit_diagnostics(audit)
            candidate_id = audit.get("candidate_id")
            if isinstance(candidate_id, str):
                item["candidate_id"] = candidate_id
                candidate_parts = candidate_id.split(":")
                if candidate_parts:
                    item["strategy"] = candidate_parts[0]
                if len(candidate_parts) >= 2 and candidate_parts[1] in {"long", "short"}:
                    item["direction"] = candidate_parts[1]
            item["ranking_role"] = "geometry_rejected"
            item["replay_source"] = "geometry_rejected"
            diagnostics.append(item)

    unique: list[dict[str, object]] = []
    seen: set[tuple[object, ...]] = set()
    for item in diagnostics:
        key = (
            item.get("candidate_id"),
            item.get("ranking_role"),
            item.get("strategy"),
            item.get("direction"),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def _decision_confirmation_diagnostics(
    *, analysis: object, setup: object | None
) -> dict[str, object | None] | None:
    candidates = _candidate_diagnostics(analysis)
    if setup is None:
        if not candidates:
            return None
        return {
            "source": "best_available_candidate",
            "candidate_id": candidates[0].get("candidate_id"),
            **_confirmation_diagnostics(candidates[0]),
        }

    setup_diagnostics = _confirmation_diagnostics(_jsonable(setup))
    setup_strategy = _enum_value(getattr(setup, "strategy", None))
    setup_direction = _enum_value(getattr(setup, "direction", None))
    matching_candidate = next(
        (
            candidate
            for candidate in candidates
            if candidate.get("strategy") == setup_strategy
            and candidate.get("direction") == setup_direction
        ),
        None,
    )
    if matching_candidate is None:
        return setup_diagnostics

    candidate_diagnostics = _confirmation_diagnostics(matching_candidate)
    merged = dict(candidate_diagnostics)
    merged.update({key: value for key, value in setup_diagnostics.items() if value is not None})
    merged["source"] = "setup_with_candidate_fallback"
    merged["candidate_id"] = matching_candidate.get("candidate_id")
    return merged


def _tp1_approached_before_stop(
    *, serialized: Mapping[str, object], metadata: Mapping[str, object], signal: object
) -> bool | None:
    del signal
    outcome = serialized.get("outcome")
    if getattr(outcome, "value", outcome) != "stop":
        return None
    explicit = metadata.get("tp1_approached_before_stop")
    return explicit if isinstance(explicit, bool) else None


def _mapping_value(values: Mapping[str, object], key: str) -> float | None:
    value = values.get(key)
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    numeric = float(value)
    return numeric if math.isfinite(numeric) and numeric > 0.0 else None


def _enum_value(value: object) -> str | None:
    if value is None:
        return None
    raw = getattr(value, "value", value)
    return str(raw)


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


def _enriched_trade_diagnostics(
    *,
    signal: object,
    metadata: Mapping[str, object],
    fee_pct: float,
    slippage_pct: float,
) -> dict[str, object]:
    base = (
        dict(signal.get("diagnostics", {}))
        if isinstance(signal, Mapping) and isinstance(signal.get("diagnostics"), Mapping)
        else {}
    )
    if not isinstance(signal, Mapping):
        return base
    entry = signal.get("entry_price")
    stop = signal.get("stop_price")
    target = signal.get("target_price")
    if not (
        isinstance(entry, (int, float))
        and not isinstance(entry, bool)
        and isinstance(stop, (int, float))
        and not isinstance(stop, bool)
        and isinstance(target, (int, float))
        and not isinstance(target, bool)
    ):
        return base
    entry_value = float(entry)
    stop_value = float(stop)
    target_value = float(target)
    risk = abs(entry_value - stop_value)
    if risk <= 0.0:
        return base
    gross_tp1_r = abs(target_value - entry_value) / risk
    modeled_cost = (entry_value + target_value) * ((fee_pct + slippage_pct) / 100.0)
    base["gross_tp1_r"] = gross_tp1_r
    base["modeled_round_trip_cost"] = modeled_cost
    base["modeled_round_trip_cost_r"] = modeled_cost / risk
    base["net_tp1_r"] = gross_tp1_r - modeled_cost / risk
    base["fee_pct"] = fee_pct
    base["slippage_pct"] = slippage_pct
    base["maximum_favorable_excursion_r"] = metadata.get("maximum_favorable_excursion_r")
    base["maximum_adverse_excursion_r"] = metadata.get("maximum_adverse_excursion_r")
    return base


def _r_progress_diagnostics(
    *, metadata: Mapping[str, object], diagnostics: Mapping[str, object]
) -> dict[str, object | None]:
    mfe = metadata.get("maximum_favorable_excursion_r")
    if not isinstance(mfe, (int, float)) or isinstance(mfe, bool):
        return {
            "reached_0_5r": None,
            "reached_1r": None,
            "reached_1_5r": None,
            "reached_2r": None,
            "reached_3r": None,
            "tp1_progress_ratio": None,
        }
    mfe_value = float(mfe)
    tp1_r = diagnostics.get("net_tp1_r")
    if not isinstance(tp1_r, (int, float)) or isinstance(tp1_r, bool) or tp1_r <= 0.0:
        tp1_r = diagnostics.get("gross_tp1_r")
    tp1_progress = (
        mfe_value / float(tp1_r)
        if isinstance(tp1_r, (int, float)) and not isinstance(tp1_r, bool) and float(tp1_r) > 0.0
        else None
    )
    return {
        "reached_0_5r": mfe_value >= 0.5,
        "reached_1r": mfe_value >= 1.0,
        "reached_1_5r": mfe_value >= 1.5,
        "reached_2r": mfe_value >= 2.0,
        "reached_3r": mfe_value >= 3.0,
        "tp1_progress_ratio": (None if tp1_progress is None else round(tp1_progress, 12)),
    }


def _report_metrics(report: object) -> dict[str, object]:
    payload = _jsonable(report)
    if not isinstance(payload, dict):
        raise TypeError("backtest report must serialize to an object")
    payload["trades"] = []
    if payload.get("total_trades") == 0:
        for key in (
            "win_rate",
            "loss_rate",
            "breakeven_rate",
            "average_win",
            "average_loss",
            "average_risk_reward",
            "expectancy",
            "maximum_drawdown",
            "profit_factor",
        ):
            payload[key] = None
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            for key in ("entry_fill_rate", "average_mfe_r", "average_mae_r"):
                metadata[key] = None
    return payload


def _diagnostic_report_metrics(report: object) -> dict[str, object]:
    """Return shadow metrics without pretending overlapping signals form a portfolio."""

    payload = _report_metrics(report)
    payload["maximum_drawdown"] = None
    metadata = payload.get("metadata")
    if isinstance(metadata, dict):
        metadata["maximum_drawdown_r"] = None
        metadata["drawdown_evaluable"] = False
    return payload


def _canonical_trade_records(
    trades: object,
    *,
    calibration_records: list[dict[str, object]],
    partition_by_time: Mapping[str, str],
    fee_pct: float,
    slippage_pct: float,
) -> list[dict[str, object]]:
    if not isinstance(trades, tuple | list):
        return []
    calibration_by_time = {
        str(record.get("decision_time")): record for record in calibration_records
    }
    records: list[dict[str, object]] = []
    for index, trade in enumerate(trades, start=1):
        serialized = _jsonable(trade)
        if not isinstance(serialized, dict):
            continue
        signal = serialized.get("signal")
        generated_at = signal.get("generated_at") if isinstance(signal, Mapping) else None
        decision_time = str(generated_at or "")
        calibration = calibration_by_time.get(decision_time, {})
        metadata = serialized.get("metadata")
        metadata_map = metadata if isinstance(metadata, Mapping) else {}
        target_count = int(metadata_map.get("partial_target_count", 0) or 0)
        enriched_diagnostics = _enriched_trade_diagnostics(
            signal=signal,
            metadata=metadata_map,
            fee_pct=fee_pct,
            slippage_pct=slippage_pct,
        )
        serialized.update(
            {
                "trade_number": index,
                "decision_time": decision_time or None,
                "partition": partition_by_time.get(decision_time),
                "opportunity_id": (
                    signal.get("candidate_id")
                    if isinstance(signal, Mapping) and signal.get("candidate_id")
                    else calibration.get("opportunity_id")
                ),
                "sequence_role": calibration.get("sequence_role"),
                "actionability_state": calibration.get("actionability_state"),
                "replay_reason_code": calibration.get("replay_reason_code"),
                "canonical_portfolio": calibration.get("canonical_portfolio"),
                "targets_hit": target_count,
                "maximum_favorable_excursion_r": metadata_map.get("maximum_favorable_excursion_r"),
                "maximum_adverse_excursion_r": metadata_map.get("maximum_adverse_excursion_r"),
                "counterfactual_path_mfe_r": metadata_map.get("counterfactual_path_mfe_r"),
                "counterfactual_path_mae_r": metadata_map.get("counterfactual_path_mae_r"),
                "direction_correct_at_horizon": metadata_map.get("direction_correct_at_horizon"),
                "entry_follow_through": metadata_map.get("entry_follow_through"),
                "same_candle_stop_target_ambiguous": metadata_map.get(
                    "same_candle_stop_target_ambiguous"
                ),
                "target_touched": metadata_map.get("target_touched"),
                "net_profitable_target": metadata_map.get("net_profitable_target"),
                "diagnostics": enriched_diagnostics,
                "r_progress": _r_progress_diagnostics(
                    metadata=metadata_map,
                    diagnostics=enriched_diagnostics,
                ),
                "tp1_approached_before_stop": _tp1_approached_before_stop(
                    serialized=serialized,
                    metadata=metadata_map,
                    signal={"diagnostics": enriched_diagnostics},
                ),
            }
        )
        records.append(serialized)
    return records


def _outcome_distribution(trades: object) -> dict[str, object]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    outcome_counts = {
        "target": 0,
        "stop": 0,
        "expired": 0,
        "missed_entry": 0,
        "pre_entry_invalidated": 0,
        "activation_expired": 0,
    }
    target_counts = {"tp1_hit_count": 0, "tp2_hit_count": 0, "tp3_hit_count": 0}
    ambiguity_count = 0
    profitable_target_count = 0
    for trade in values:
        outcome = getattr(getattr(trade, "outcome", None), "value", None)
        if outcome in outcome_counts:
            outcome_counts[outcome] += 1
        metadata = getattr(trade, "metadata", {})
        target_count = (
            int(metadata.get("partial_target_count", 0) or 0)
            if isinstance(metadata, Mapping)
            else 0
        )
        for threshold, key in (
            (1, "tp1_hit_count"),
            (2, "tp2_hit_count"),
            (3, "tp3_hit_count"),
        ):
            if target_count >= threshold:
                target_counts[key] += 1
        if isinstance(metadata, Mapping):
            ambiguity_count += metadata.get("same_candle_stop_target_ambiguous") is True
            profitable_target_count += metadata.get("net_profitable_target") is True

    total = len(values)
    return {
        **outcome_counts,
        **target_counts,
        "net_profitable_target_count": profitable_target_count,
        "same_candle_stop_target_ambiguity_count": ambiguity_count,
        "stop_rate": outcome_counts["stop"] / total if total else None,
        "missed_entry_rate": outcome_counts["missed_entry"] / total if total else None,
        "expired_rate": outcome_counts["expired"] / total if total else None,
        "tp1_hit_rate": target_counts["tp1_hit_count"] / total if total else None,
        "tp2_hit_rate": target_counts["tp2_hit_count"] / total if total else None,
        "tp3_hit_rate": target_counts["tp3_hit_count"] / total if total else None,
    }


def _execution_metrics(trades: object) -> dict[str, object]:
    """Return fill-only performance without counting unfilled plans as trades."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    filled = tuple(
        trade
        for trade in values
        if isinstance(getattr(trade, "metadata", None), Mapping)
        and trade.metadata.get("entry_filled") is True
    )
    report = summarize_trades(filled)
    metrics = _report_metrics(report)
    return {
        "signal_outcome_count": len(values),
        "filled_trade_count": len(filled),
        "fill_rate": len(filled) / len(values) if values else None,
        "win_rate": metrics.get("win_rate"),
        "loss_rate": metrics.get("loss_rate"),
        "expectancy": metrics.get("expectancy"),
        "profit_factor": metrics.get("profit_factor"),
        "net_profit": metrics.get("net_profit"),
        "maximum_drawdown": metrics.get("maximum_drawdown"),
        "average_risk_reward": metrics.get("average_risk_reward"),
    }


def _activation_metrics(trades: object) -> dict[str, object]:
    """Measure future-plan activation separately from post-fill execution."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    activated = 0
    filled = 0
    invalidated = 0
    expired = 0
    missed = 0
    activation_waits: list[float] = []
    for trade in values:
        metadata = getattr(trade, "metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        activation_outcome = metadata.get("activation_outcome")
        terminal_state = metadata.get("terminal_state")
        if activation_outcome == "triggered":
            activated += 1
        if metadata.get("entry_filled") is True:
            filled += 1
        if terminal_state == "pre_entry_invalidated":
            invalidated += 1
        elif terminal_state == "never_activated":
            expired += 1
        elif terminal_state == "missed_trigger":
            missed += 1
        wait = metadata.get("activation_wait_candles")
        if isinstance(wait, int | float) and not isinstance(wait, bool):
            activation_waits.append(float(wait))

    total = len(values)
    return {
        "future_setup_count": total,
        "activation_count": activated,
        "activation_rate": activated / total if total else None,
        "fill_count": filled,
        "fill_rate": filled / total if total else None,
        "pre_entry_invalidation_count": invalidated,
        "activation_expiry_count": expired,
        "missed_trigger_count": missed,
        "average_activation_wait_candles": (
            sum(activation_waits) / len(activation_waits) if activation_waits else None
        ),
    }


def _decision_funnel_metrics(
    *,
    decision_point_count: int,
    production_signals: int,
    conditional_signals: int,
    no_trade_decisions: list[dict[str, object]],
    production_trades: object,
    conditional_trades: object,
) -> dict[str, object]:
    """Describe how chronological decisions move through the setup funnel."""

    production_values = (
        tuple(production_trades) if isinstance(production_trades, tuple | list) else ()
    )
    conditional_values = (
        tuple(conditional_trades) if isinstance(conditional_trades, tuple | list) else ()
    )
    production_fills = sum(
        isinstance(getattr(trade, "metadata", None), Mapping)
        and trade.metadata.get("entry_filled") is True
        for trade in production_values
    )
    conditional_fills = sum(
        isinstance(getattr(trade, "metadata", None), Mapping)
        and trade.metadata.get("entry_filled") is True
        for trade in conditional_values
    )
    true_no_setup = 0
    for decision in no_trade_decisions:
        reasons = decision.get("reasons")
        reason_values = reasons if isinstance(reasons, list | tuple) else ()
        if "canonical_opportunity_pending_activation" not in reason_values:
            true_no_setup += 1
    return {
        "decision_point_count": decision_point_count,
        "immediate_setup_count": production_signals,
        "future_setup_count": conditional_signals,
        "setup_found_count": production_signals + conditional_signals,
        "true_no_setup_count": true_no_setup,
        "immediate_setup_rate": (
            production_signals / decision_point_count if decision_point_count else None
        ),
        "future_setup_rate": (
            conditional_signals / decision_point_count if decision_point_count else None
        ),
        "setup_coverage_rate": (
            (production_signals + conditional_signals) / decision_point_count
            if decision_point_count
            else None
        ),
        "immediate_fill_count": production_fills,
        "future_fill_count": conditional_fills,
        "total_fill_count": production_fills + conditional_fills,
    }


def _risk_and_excursion(trades: object) -> dict[str, object]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    mfe_values: list[float] = []
    mae_values: list[float] = []
    path_mfe_values: list[float] = []
    path_mae_values: list[float] = []
    for trade in values:
        metadata = getattr(trade, "metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        mfe = metadata.get("maximum_favorable_excursion_r")
        mae = metadata.get("maximum_adverse_excursion_r")
        if isinstance(mfe, int | float) and not isinstance(mfe, bool):
            mfe_values.append(float(mfe))
        if isinstance(mae, int | float) and not isinstance(mae, bool):
            mae_values.append(float(mae))
        path_mfe = metadata.get("counterfactual_path_mfe_r")
        path_mae = metadata.get("counterfactual_path_mae_r")
        if isinstance(path_mfe, int | float) and not isinstance(path_mfe, bool):
            path_mfe_values.append(float(path_mfe))
        if isinstance(path_mae, int | float) and not isinstance(path_mae, bool):
            path_mae_values.append(float(path_mae))

    return {
        "average_mfe_r": sum(mfe_values) / len(mfe_values) if mfe_values else None,
        "average_mae_r": sum(mae_values) / len(mae_values) if mae_values else None,
        "best_mfe_r": max(mfe_values) if mfe_values else None,
        "worst_mae_r": max(mae_values) if mae_values else None,
        "average_counterfactual_path_mfe_r": (
            sum(path_mfe_values) / len(path_mfe_values) if path_mfe_values else None
        ),
        "average_counterfactual_path_mae_r": (
            sum(path_mae_values) / len(path_mae_values) if path_mae_values else None
        ),
    }


def _shadow_source_distribution(trades: object) -> dict[str, int]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    counts: dict[str, int] = {}
    for trade in values:
        signal = getattr(trade, "signal", None)
        source = getattr(signal, "replay_source", None)
        if isinstance(source, str):
            counts[source] = counts.get(source, 0) + 1
    return counts


def _direction_accuracy(trades: object) -> dict[str, object]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    results: list[bool] = []
    for trade in values:
        metadata = getattr(trade, "metadata", None)
        value = (
            metadata.get("direction_correct_at_horizon") if isinstance(metadata, Mapping) else None
        )
        if isinstance(value, bool):
            results.append(value)
    correct = sum(results)
    return {
        "evaluable_count": len(results),
        "correct_count": correct,
        "incorrect_count": len(results) - correct,
        "accuracy": correct / len(results) if results else None,
    }


__all__ = ["register_backtesting_commands"]
