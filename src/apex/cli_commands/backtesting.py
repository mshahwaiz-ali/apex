"""Focused public chronological backtest command."""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass
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
from apex.application.discovery_contracts import DiscoverySetup
from apex.application.opportunity_portfolio import (
    ActionabilityState,
    SequenceRole,
    build_actionability_state_assessment,
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
from apex.presentation.backtest_output import render_backtest
from apex.presentation.terminal import emit_terminal
from apex.research.metrics import (
    deflated_sharpe_probability,
    probability_of_backtest_overfitting,
)


@dataclass(frozen=True, slots=True)
class _ReplayDecision:
    """Canonical decision selected for one historical analysis point."""

    setup: DiscoverySetup | None
    opportunity_id: str | None
    sequence_role: str | None
    actionability_state: str | None
    reason_code: str
    canonical_portfolio: bool


_EXECUTABLE_REPLAY_STATES = frozenset(
    {
        ActionabilityState.EXECUTE_NOW,
        ActionabilityState.AGGRESSIVE_NOW,
    }
)


def _select_replay_decision(analysis: object) -> _ReplayDecision:
    """Select one already-executable canonical opportunity without inventing fills."""

    portfolio = getattr(analysis, "opportunity_portfolio", None)
    if portfolio is None:
        assessment = getattr(analysis, "assessment", None)
        setup = getattr(assessment, "setup", None)
        return _ReplayDecision(
            setup=setup if isinstance(setup, DiscoverySetup) else None,
            opportunity_id=(setup.candidate_id if isinstance(setup, DiscoverySetup) else None),
            sequence_role=(
                SequenceRole.CURRENT.value if isinstance(setup, DiscoverySetup) else None
            ),
            actionability_state=None,
            reason_code=(
                "legacy_selected_setup"
                if isinstance(setup, DiscoverySetup)
                else "legacy_no_selected_setup"
            ),
            canonical_portfolio=False,
        )

    observed_states: list[ActionabilityState] = []
    opportunities = tuple(getattr(portfolio, "opportunities", ()))
    for opportunity in opportunities:
        setup = getattr(opportunity, "setup", None)
        role = getattr(opportunity, "sequence_role", None)
        if not isinstance(setup, DiscoverySetup) or not isinstance(role, SequenceRole):
            continue
        actionability = build_actionability_state_assessment(
            setup,
            sequence_role=role,
        )
        observed_states.append(actionability.state)
        if (
            role is SequenceRole.CURRENT
            and actionability.state in _EXECUTABLE_REPLAY_STATES
            and setup.execution_allowed_now
            and not actionability.has_blocking_issue
        ):
            return _ReplayDecision(
                setup=setup,
                opportunity_id=str(getattr(opportunity, "opportunity_id", setup.candidate_id)),
                sequence_role=role.value,
                actionability_state=actionability.state.value,
                reason_code="canonical_executable_opportunity",
                canonical_portfolio=True,
            )

    reason_code = "canonical_no_executable_opportunity"
    if ActionabilityState.MISSED_OR_CHASING in observed_states:
        reason_code = "canonical_opportunity_missed_or_chasing"
    elif ActionabilityState.INVALIDATED in observed_states:
        reason_code = "canonical_opportunity_invalidated"
    elif observed_states:
        reason_code = "canonical_opportunity_pending_activation"

    return _ReplayDecision(
        setup=None,
        opportunity_id=None,
        sequence_role=None,
        actionability_state=None,
        reason_code=reason_code,
        canonical_portfolio=True,
    )


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
                    methodology_gate_mode=context.settings.methodology_gate_mode,
                    futures_evidence_enabled=context.settings.futures_evidence_enabled,
                )
                replay_decision = _select_replay_decision(analysis)
                setup = replay_decision.setup
                calibration_records.append(
                    _calibration_record(
                        analysis=analysis,
                        partition=partition,
                        replay_decision=replay_decision,
                    )
                )
                if setup is None:
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
            "schema_version": 3,
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
            "trades": _canonical_trade_records(
                report.trades,
                calibration_records=calibration_records,
                partition_by_time=partition_by_time,
            ),
            "metrics": _report_metrics(report),
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
        "schema_version": 1,
        "symbol": serialized.get("symbol"),
        "decision_time": serialized.get("generated_at"),
        "partition": partition,
        "production_decision": serialized.get("decision"),
        "strategy": None if setup is None else setup.strategy.value,
        "opportunity_id": resolved_decision.opportunity_id,
        "sequence_role": resolved_decision.sequence_role,
        "actionability_state": resolved_decision.actionability_state,
        "replay_reason_code": resolved_decision.reason_code,
        "canonical_portfolio": resolved_decision.canonical_portfolio,
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
        "entry_geometry": None if setup is None else _jsonable(setup.entry),
        "stop_geometry": None if setup is None else _jsonable(setup.stop_loss),
        "target_geometry": None if setup is None else _jsonable(setup.take_profits),
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


def _canonical_trade_records(
    trades: object,
    *,
    calibration_records: list[dict[str, object]],
    partition_by_time: Mapping[str, str],
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
        serialized.update(
            {
                "trade_number": index,
                "decision_time": decision_time or None,
                "partition": partition_by_time.get(decision_time),
                "opportunity_id": calibration.get("opportunity_id"),
                "sequence_role": calibration.get("sequence_role"),
                "actionability_state": calibration.get("actionability_state"),
                "replay_reason_code": calibration.get("replay_reason_code"),
                "canonical_portfolio": calibration.get("canonical_portfolio"),
                "targets_hit": target_count,
                "maximum_favorable_excursion_r": metadata_map.get("maximum_favorable_excursion_r"),
                "maximum_adverse_excursion_r": metadata_map.get("maximum_adverse_excursion_r"),
            }
        )
        records.append(serialized)
    return records


def _outcome_distribution(trades: object) -> dict[str, object]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    outcome_counts = {"target": 0, "stop": 0, "expired": 0, "missed_entry": 0}
    target_counts = {"tp1_hit_count": 0, "tp2_hit_count": 0, "tp3_hit_count": 0}
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

    total = len(values)
    return {
        **outcome_counts,
        **target_counts,
        "stop_rate": outcome_counts["stop"] / total if total else 0.0,
        "missed_entry_rate": outcome_counts["missed_entry"] / total if total else 0.0,
        "expired_rate": outcome_counts["expired"] / total if total else 0.0,
        "tp1_hit_rate": target_counts["tp1_hit_count"] / total if total else 0.0,
        "tp2_hit_rate": target_counts["tp2_hit_count"] / total if total else 0.0,
        "tp3_hit_rate": target_counts["tp3_hit_count"] / total if total else 0.0,
    }


def _risk_and_excursion(trades: object) -> dict[str, object]:
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    mfe_values: list[float] = []
    mae_values: list[float] = []
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

    return {
        "average_mfe_r": sum(mfe_values) / len(mfe_values) if mfe_values else 0.0,
        "average_mae_r": sum(mae_values) / len(mae_values) if mae_values else 0.0,
        "best_mfe_r": max(mfe_values) if mfe_values else 0.0,
        "worst_mae_r": max(mae_values) if mae_values else 0.0,
    }


__all__ = ["register_backtesting_commands"]
