"""Focused public chronological backtest command."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Mapping
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
from apex.application.configuration_identity import configuration_metadata
from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_geometry_runtime import (
    geometry_execution_costs_from_settings,
)
from apex.application.methodology_identity import methodology_identity_payload
from apex.application.portfolio_retention import setup_geometry_fingerprint
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
from apex.domain.futures_evidence import FundingRateSnapshot
from apex.presentation import OutputMode, normalize_cli_output_mode
from apex.presentation.backtest_output import render_backtest
from apex.presentation.terminal import emit_terminal
from apex.research.campaign import read_funding_rate_archive
from apex.research.metrics import deflated_sharpe_probability
from apex.strategies import StrategyType, TradeDirection

_ReplayDecision = CanonicalOpportunityDecision
_select_replay_decision = select_canonical_opportunity_decision


def _conditional_replay_authorized(setup: DiscoverySetup | None) -> bool:
    "Only canonical future-authorized setups may enter conditional replay."

    return (
        setup is not None and setup.future_activation_allowed and setup.conditional_plan is not None
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
                max=200,
                help="Chronological non-overlapping decisions in the replay campaign.",
            ),
        ] = 5,
        funding_pct: Annotated[
            float,
            typer.Option("--funding-pct", min=0.0, help="Optional modeled funding drag."),
        ] = 0.0,
        funding_archive: Annotated[
            Path | None,
            typer.Option(
                "--funding-archive",
                exists=True,
                dir_okay=False,
                help="Verified Binance monthly funding ZIP for event-level replay costs.",
            ),
        ] = None,
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
            funding_events: tuple[FundingRateSnapshot, ...] = ()
            funding_history_reason = "futures_evidence_disabled"

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
                if funding_archive is not None:
                    fetched_funding = read_funding_rate_archive(
                        funding_archive,
                        symbol=normalized_symbol,
                    )
                    funding_events = tuple(
                        item
                        for item in fetched_funding
                        if anchor_time is None or item.funding_time <= anchor_time
                    )
                    funding_history_reason = (
                        "available:checksum_archive_supplied_by_operator"
                        if funding_events
                        else "archive_has_no_events_in_requested_point_in_time_window"
                    )
                elif context.settings.futures_evidence_enabled:
                    try:
                        fetched_funding = services.futures_evidence.fetch_funding_rates(
                            normalized_symbol,
                            limit=500,
                        )
                        funding_events = tuple(
                            item
                            for item in fetched_funding
                            if anchor_time is None or item.funding_time <= anchor_time
                        )
                        funding_history_reason = (
                            "available"
                            if funding_events
                            else "no_events_in_requested_point_in_time_window"
                        )
                    except MarketDataProviderError as exc:
                        funding_history_reason = f"unavailable:{type(exc).__name__}"

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
            previous_market_regime: str | None = None
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
                    previous_market_regime=previous_market_regime,
                )
                intelligence = analysis.market_intelligence or {}
                regime_payload = intelligence.get("regime")
                if isinstance(regime_payload, Mapping):
                    regime_state = regime_payload.get("state")
                    if isinstance(regime_state, str):
                        previous_market_regime = regime_state
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
                    if _conditional_replay_authorized(setup):
                        assert setup is not None
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

        market_costs = context.settings.geometry_execution.market
        config = BacktestConfig(
            maximum_holding_candles=replay_candles,
            funding_pct=funding_pct,
            entry_fee_pct=(None if market_costs is None else market_costs.entry_fee_pct),
            exit_fee_pct=(None if market_costs is None else market_costs.exit_fee_pct),
            entry_slippage_pct=(None if market_costs is None else market_costs.entry_slippage_pct),
            exit_slippage_pct=(None if market_costs is None else market_costs.exit_slippage_pct),
            cost_profile=(
                "conservative_market" if market_costs is not None else "legacy_symmetric"
            ),
            include_observed_spread_in_cost=(
                context.settings.geometry_execution.include_observed_spread_in_cost
            ),
        )
        study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=_sorted_replay_signals(signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                funding_by_symbol={normalized_symbol: funding_events},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:campaign",
            )
        )
        conditional_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=_sorted_replay_signals(conditional_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                funding_by_symbol={normalized_symbol: funding_events},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:conditional-campaign",
            )
        )
        opportunity_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=_sorted_replay_signals(opportunity_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                funding_by_symbol={normalized_symbol: funding_events},
                config=config,
                dataset_id=f"{normalized_symbol}:{replay_timeframe}:opportunity-campaign",
            )
        )
        shadow_study = HistoricalBacktestRunner().run(
            BacktestRequest(
                signals=_sorted_replay_signals(shadow_signals),
                candles_by_symbol={normalized_symbol: replay_series.candles},
                funding_by_symbol={normalized_symbol: funding_events},
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
                "candidate_id": trade.signal.candidate_id,
                "replay_source": trade.signal.replay_source,
                "replay_class": replay_class,
            }

        replay_outcomes = _replay_outcomes_by_decision(
            production_trades=report.trades,
            conditional_trades=conditional_report.trades,
            replay_record=replay_record,
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
                        "candidate_id": None,
                        "replay_source": None,
                        "replay_class": "none",
                    },
                ),
            }
            for record in calibration_records
        ]
        partition_by_time = {
            item["decision_time"]: item["partition"] for item in decision_partitions
        }
        filled_report_trades = _filled_execution_trades(report.trades)
        partition_metrics = {
            partition: _report_metrics(
                summarize_trades(
                    tuple(
                        trade
                        for trade in filled_report_trades
                        if partition_by_time.get(trade.signal.generated_at.isoformat()) == partition
                    )
                )
            )
            for partition in ("training", "validation", "final_test")
        }
        final_returns = tuple(
            trade.realized_r_multiple
            for trade in filled_report_trades
            if partition_by_time.get(trade.signal.generated_at.isoformat()) == "final_test"
        )
        attempted_configurations = len(
            {
                (
                    record.get("strategy"),
                    record.get("setup_geometry_fingerprint"),
                )
                for record in calibration_records
                if record.get("strategy") is not None
            }
        )
        promotion_statistics = {
            "deflated_sharpe_probability": (
                deflated_sharpe_probability(
                    final_returns,
                    trials=max(1, attempted_configurations),
                )
                if final_returns
                else None
            ),
            "probability_backtest_overfitting": None,
            "probability_backtest_overfitting_reason": (
                "insufficient_comparisons"
                if attempted_configurations < 2
                else "requires_fold_level_configuration_vectors"
            ),
            "attempted_configurations": attempted_configurations,
        }
        decision_funnel = _decision_funnel_metrics(
            decision_point_count=decision_points,
            production_signals=study.generated_signal_count,
            conditional_signals=conditional_study.generated_signal_count,
            no_trade_decisions=no_trade_decisions,
            production_trades=report.trades,
            conditional_trades=conditional_report.trades,
        )
        legacy_fee_pct = (config.effective_entry_fee_pct + config.effective_exit_fee_pct) / 2.0
        legacy_slippage_pct = (
            config.effective_entry_slippage_pct + config.effective_exit_slippage_pct
        ) / 2.0
        payload = {
            "schema_version": 6,
            "legacy_schema_version": 5,
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
                fee_pct=legacy_fee_pct,
                slippage_pct=legacy_slippage_pct,
            ),
            "metrics": _report_metrics(summarize_trades(_filled_execution_trades(report.trades))),
            "execution_metrics": _execution_metrics(report.trades),
            "decision_funnel": decision_funnel,
            "outcome_distribution": _outcome_distribution(report.trades),
            "risk_and_excursion": _risk_and_excursion(report.trades),
            "thesis_metrics": _thesis_metrics(report.trades),
            "stop_breach_metrics": _stop_breach_metrics(report.trades),
            "sweep_reclaim_metrics": _sweep_reclaim_metrics(report.trades),
            "execution_assumptions": {
                "fee_pct": config.fee_pct,
                "slippage_pct": config.slippage_pct,
                "funding_pct": config.funding_pct,
                "funding_pct_authority": "manual_stress_override",
                "historical_funding_event_count": len(funding_events),
                "historical_funding_status": funding_history_reason,
                "entry_fee_pct": config.effective_entry_fee_pct,
                "exit_fee_pct": config.effective_exit_fee_pct,
                "entry_slippage_pct": config.effective_entry_slippage_pct,
                "exit_slippage_pct": config.effective_exit_slippage_pct,
                "cost_profile": config.cost_profile,
                "include_observed_spread_in_cost": (config.include_observed_spread_in_cost),
                "maximum_holding_candles": config.maximum_holding_candles,
                "conservative_intrabar": config.conservative_intrabar,
                "methodology_gate_mode": context.settings.methodology_gate_mode,
            },
            "metrics_by_partition": partition_metrics,
            "promotion_statistics": promotion_statistics,
            "calibration_authoritative": False,
            "metric_authority": {
                "canonical_performance": "authoritative_for_this_replay_only",
                "calibration": "non_authoritative_until_untouched_outcomes",
                "promotion": "not_authorized_by_single_symbol_backtest",
            },
            "methodology_identity": methodology_identity_payload(),
            "geometry_population": _unique_geometry_population(calibration_records),
            "conditional_replay": {
                "signal_count": conditional_study.generated_signal_count,
                "trades": _canonical_trade_records(
                    conditional_report.trades,
                    calibration_records=calibration_records,
                    partition_by_time=partition_by_time,
                    fee_pct=legacy_fee_pct,
                    slippage_pct=legacy_slippage_pct,
                ),
                "metrics": _report_metrics(
                    summarize_trades(_filled_execution_trades(conditional_report.trades))
                ),
                "activation_metrics": _activation_metrics(conditional_report.trades),
                "execution_metrics": _execution_metrics(conditional_report.trades),
                "outcome_distribution": _outcome_distribution(conditional_report.trades),
                "risk_and_excursion": _risk_and_excursion(conditional_report.trades),
                "thesis_metrics": _thesis_metrics(conditional_report.trades),
                "stop_breach_metrics": _stop_breach_metrics(conditional_report.trades),
                "sweep_reclaim_metrics": _sweep_reclaim_metrics(conditional_report.trades),
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
                    fee_pct=legacy_fee_pct,
                    slippage_pct=legacy_slippage_pct,
                ),
                "metrics": _diagnostic_report_metrics(opportunity_report),
                "activation_metrics": _activation_metrics(opportunity_report.trades),
                "execution_metrics": _execution_metrics(opportunity_report.trades),
                "outcome_distribution": _outcome_distribution(opportunity_report.trades),
                "risk_and_excursion": _risk_and_excursion(opportunity_report.trades),
                "thesis_metrics": _thesis_metrics(opportunity_report.trades),
                "stop_breach_metrics": _stop_breach_metrics(opportunity_report.trades),
                "sweep_reclaim_metrics": _sweep_reclaim_metrics(opportunity_report.trades),
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
                    fee_pct=legacy_fee_pct,
                    slippage_pct=legacy_slippage_pct,
                ),
                "metrics": _diagnostic_report_metrics(shadow_report),
                "outcome_distribution": _outcome_distribution(shadow_report.trades),
                "risk_and_excursion": _risk_and_excursion(shadow_report.trades),
                "source_distribution": _shadow_source_distribution(shadow_report.trades),
                "direction_accuracy": _direction_accuracy(shadow_report.trades),
                "geometry_rejection_summary": _geometry_rejection_summary(calibration_records),
                "thesis_metrics": _thesis_metrics(shadow_report.trades),
                "stop_breach_metrics": _stop_breach_metrics(shadow_report.trades),
                "sweep_reclaim_metrics": _sweep_reclaim_metrics(shadow_report.trades),
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
        payload.update(configuration_metadata(context.settings.model_dump(mode="json")))
        _classify_replay_trade_records(
            payload, section="conditional_replay", replay_class="conditional"
        )
        _classify_replay_trade_records(
            payload, section="opportunity_replay", replay_class="opportunity"
        )
        _classify_replay_trade_records(payload, section="shadow_replay", replay_class="shadow")
        payload["evaluation_outcomes"] = _evaluation_outcome_rows(payload)
        if len(report.trades) == 1:
            payload["trade"] = _jsonable(report.trades[0])
        if report_file is not None:
            report_file.parent.mkdir(parents=True, exist_ok=True)
            report_file.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"
            )
        _emit(payload, render_backtest(payload), output_mode)


def _classify_replay_trade_records(
    payload: dict[str, object],
    *,
    section: str,
    replay_class: str,
) -> None:
    """Mark diagnostic replay records as non-canonical portfolio observations."""

    section_payload = payload.get(section)
    if not isinstance(section_payload, dict):
        return
    trades = section_payload.get("trades")
    if not isinstance(trades, list):
        return
    for record in trades:
        if not isinstance(record, dict):
            continue
        record["canonical_portfolio"] = False
        record["replay_class"] = replay_class


def _geometry_rejection_summary(
    calibration_records: list[dict[str, object]],
) -> dict[str, object]:
    """Aggregate geometry rejection causes without changing production selection."""

    code_counts: dict[str, int] = {}
    strategy_counts: dict[str, int] = {}
    legacy_lane_counts: dict[str, int] = {}
    measured_lane_counts: dict[str, int] = {}
    execution_cost_profile_counts: dict[str, int] = {}
    cost_profile_reason_counts: dict[str, int] = {}
    lane_change_count = 0
    result_change_count = 0
    rejected_candidate_count = 0

    numeric_fields = (
        "gross_tp1_reward_to_risk",
        "net_tp1_reward_to_risk",
        "stop_to_cost_ratio",
        "target_to_cost_ratio",
        "tp1_distance_atr",
        "maximum_tp1_distance_atr",
        "expected_cost_pct",
        "observed_spread_pct",
    )
    numeric_totals = {field: 0.0 for field in numeric_fields}
    numeric_counts = {field: 0 for field in numeric_fields}

    for record in calibration_records:
        diagnostics = record.get("candidate_diagnostics")
        if not isinstance(diagnostics, list):
            continue
        for candidate in diagnostics:
            if not isinstance(candidate, dict):
                continue
            codes = candidate.get("geometry_rejection_codes")
            if not isinstance(codes, list) or not codes:
                continue

            rejected_candidate_count += 1
            for code in codes:
                if isinstance(code, str) and code:
                    code_counts[code] = code_counts.get(code, 0) + 1

            strategy = candidate.get("strategy")
            if isinstance(strategy, str) and strategy:
                strategy_counts[strategy] = strategy_counts.get(strategy, 0) + 1

            legacy_lane = candidate.get("legacy_context_lane")
            if isinstance(legacy_lane, str) and legacy_lane:
                legacy_lane_counts[legacy_lane] = legacy_lane_counts.get(legacy_lane, 0) + 1

            measured_lane = candidate.get("measured_geometry_lane")
            if isinstance(measured_lane, str) and measured_lane:
                measured_lane_counts[measured_lane] = measured_lane_counts.get(measured_lane, 0) + 1

            if candidate.get("would_change_lane") is True:
                lane_change_count += 1
            if candidate.get("would_change_geometry_result") is True:
                result_change_count += 1

            execution_cost_profile = candidate.get("execution_cost_profile")
            if isinstance(execution_cost_profile, str) and execution_cost_profile:
                execution_cost_profile_counts[execution_cost_profile] = (
                    execution_cost_profile_counts.get(execution_cost_profile, 0) + 1
                )

            cost_profile_reason = candidate.get("cost_profile_reason")
            if isinstance(cost_profile_reason, str) and cost_profile_reason:
                cost_profile_reason_counts[cost_profile_reason] = (
                    cost_profile_reason_counts.get(cost_profile_reason, 0) + 1
                )

            for field in ("expected_cost_pct", "observed_spread_pct"):
                value = candidate.get(field)
                if isinstance(value, (int, float)):
                    numeric_totals[field] += float(value)
                    numeric_counts[field] += 1

            audit = candidate.get("geometry_audit")
            if not isinstance(audit, dict):
                continue
            for field in numeric_fields:
                if field in {"expected_cost_pct", "observed_spread_pct"}:
                    continue
                value = audit.get(field)
                if isinstance(value, (int, float)):
                    numeric_totals[field] += float(value)
                    numeric_counts[field] += 1

    averages = {
        field: (numeric_totals[field] / numeric_counts[field] if numeric_counts[field] else None)
        for field in numeric_fields
    }
    return {
        "rejected_candidate_count": rejected_candidate_count,
        "rejection_code_counts": dict(
            sorted(code_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "strategy_counts": dict(
            sorted(strategy_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "legacy_lane_counts": dict(
            sorted(legacy_lane_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "measured_lane_counts": dict(
            sorted(measured_lane_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "execution_cost_profile_counts": dict(
            sorted(execution_cost_profile_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "cost_profile_reason_counts": dict(
            sorted(cost_profile_reason_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "would_change_lane_count": lane_change_count,
        "would_change_geometry_result_count": result_change_count,
        "averages": averages,
    }


def _emit(payload: object, text: str, output_mode: OutputMode) -> None:
    if output_mode is OutputMode.JSON:
        typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))
        return
    emit_terminal(text)


def _replay_outcomes_by_decision(
    *,
    production_trades: object,
    conditional_trades: object,
    replay_record: Callable[[SimulatedTrade, str], dict[str, object]],
) -> dict[str, dict[str, object]]:
    """Resolve one authoritative replay outcome per decision timestamp.

    Conditional replay fills gaps, while canonical production replay has
    precedence when both populations contain the same decision timestamp.
    """

    conditional_values = (
        tuple(conditional_trades) if isinstance(conditional_trades, tuple | list) else ()
    )
    production_values = (
        tuple(production_trades) if isinstance(production_trades, tuple | list) else ()
    )
    outcomes = {
        trade.signal.generated_at.isoformat(): replay_record(trade, "conditional")
        for trade in conditional_values
        if isinstance(trade, SimulatedTrade)
    }
    outcomes.update(
        {
            trade.signal.generated_at.isoformat(): replay_record(trade, "production")
            for trade in production_values
            if isinstance(trade, SimulatedTrade)
        }
    )
    return outcomes


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
        "candidate_id": None if setup is None else setup.candidate_id,
        "strategy_version": None if setup is None else setup.strategy_version,
        "setup_methodology_version": (None if setup is None else setup.methodology_version),
        "setup_geometry_fingerprint": (
            None if setup is None else list(setup_geometry_fingerprint(setup))
        ),
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
        "snapshot_identity": serialized.get("snapshot_identity"),
        "market_profile": serialized.get("market_profile"),
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
        "geometry_feasibility_diagnostics": (
            methodology_routing.get("geometry_safety_audits")
            if isinstance(methodology_routing, Mapping)
            else None
        ),
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
        entry_zone_low=_mapping_value(record.entry, "lower"),
        entry_zone_high=_mapping_value(record.entry, "upper"),
        stop=stop,
        target=targets[0],
        confidence=record.final_score,
        source=source,
        diagnostics=_ranking_diagnostics(
            record,
            entry=entry,
            stop=stop,
            target=targets[0],
            analysis=analysis,
        ),
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
        entry_zone_low=_mapping_value(item, "entry_zone_low"),
        entry_zone_high=_mapping_value(item, "entry_zone_high"),
        stop=_mapping_value(item, "executable_stop"),
        target=_mapping_value(item, "tp1_price"),
        confidence=0.0,
        source="geometry_rejected",
        diagnostics=_geometry_audit_diagnostics(item, analysis=analysis),
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
    entry_zone_low: float | None = None,
    entry_zone_high: float | None = None,
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
            entry_zone_low=entry_zone_low,
            entry_zone_high=entry_zone_high,
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


def _directional_value(value: object, *keys: str) -> object | None:
    """Read one JSON-safe decision-time value without adding strategy authority."""

    return _recursive_lookup(value, tuple(keys))


def _timeframe_directional_snapshots(value: object) -> dict[str, object]:
    """Extract compact per-timeframe evidence from serialized decision context."""

    supported_timeframes = ("1m", "3m", "5m", "15m", "30m", "1h", "4h")
    snapshots: dict[str, dict[str, object | None]] = {}

    def visit(node: object) -> None:
        if isinstance(node, Mapping):
            timeframe_value = node.get("timeframe") or node.get("interval") or node.get("name")
            timeframe = str(timeframe_value) if timeframe_value is not None else ""
            if timeframe in supported_timeframes:
                current = snapshots.setdefault(timeframe, {})
                aliases: Mapping[str, tuple[str, ...]] = {
                    "trend_direction": ("trend_direction", "trend", "direction", "trend_bias"),
                    "structure_bias": (
                        "structure_bias",
                        "market_structure",
                        "structure",
                        "structure_direction",
                    ),
                    "momentum_direction": (
                        "momentum_direction",
                        "momentum_bias",
                        "momentum",
                    ),
                    "rsi": ("rsi", "rsi_value"),
                    "rsi_slope": ("rsi_slope", "rsi_delta"),
                    "macd_direction": ("macd_direction", "macd_bias", "macd_state"),
                    "macd_histogram": ("macd_histogram", "macd_hist"),
                    "ema_alignment": (
                        "ema_alignment",
                        "ema_state",
                        "moving_average_alignment",
                    ),
                    "vwap_relationship": (
                        "vwap_relationship",
                        "vwap_state",
                        "price_vs_vwap",
                    ),
                    "volume_state": (
                        "volume_state",
                        "participation_state",
                        "volume_participation",
                    ),
                    "relative_volume": (
                        "relative_volume",
                        "rvol",
                        "relative_volume_ratio",
                    ),
                    "atr": ("atr", "average_true_range"),
                    "regime": ("regime", "market_regime", "primary_regime"),
                    "exhaustion_state": ("exhaustion_state", "exhaustion"),
                }
                for output_key, lookup_keys in aliases.items():
                    found = _recursive_lookup(node, lookup_keys)
                    if found is not None and current.get(output_key) is None:
                        current[output_key] = found
            for nested in node.values():
                visit(nested)
        elif isinstance(node, (list, tuple)):
            for nested in node:
                visit(nested)

    visit(value)
    return {
        timeframe: {
            key: field_value for key, field_value in fields.items() if field_value is not None
        }
        for timeframe, fields in snapshots.items()
        if any(field_value is not None for field_value in fields.values())
    }


def _analysis_diagnostic_context(analysis: object | None) -> Mapping[str, object]:
    """Return best-effort JSON-safe analysis context for diagnostics and tests."""

    if analysis is None:
        return {}
    try:
        serialized = _jsonable(
            serialize_symbol_analysis(analysis)  # type: ignore[arg-type]
        )
    except (AttributeError, TypeError, ValueError):
        if isinstance(analysis, Mapping):
            serialized = _jsonable(analysis)
        else:
            attributes = getattr(analysis, "__dict__", None)
            serialized = _jsonable(attributes) if isinstance(attributes, Mapping) else {}
    return serialized if isinstance(serialized, Mapping) else {}


def _enum_value(value: object) -> object | None:
    """Return a JSON-safe enum or scalar value."""

    raw = getattr(value, "value", value)
    return _jsonable(raw) if raw is not None else None


def _mapping_or_empty(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _analysis_payload(analysis: object | None) -> Mapping[str, object]:
    """Serialize a complete analysis when possible, with safe test fallbacks."""

    if analysis is None:
        return {}
    try:
        payload = _jsonable(
            serialize_symbol_analysis(analysis)  # type: ignore[arg-type]
        )
    except (AttributeError, TypeError, ValueError):
        if isinstance(analysis, Mapping):
            payload = _jsonable(analysis)
        else:
            attributes = getattr(analysis, "__dict__", None)
            payload = _jsonable(attributes) if isinstance(attributes, Mapping) else {}
    return payload if isinstance(payload, Mapping) else {}


def _strategy_signal_diagnostics(
    *,
    payload: Mapping[str, object],
    strategy: object,
) -> Mapping[str, object]:
    phase5 = _mapping_or_empty(payload.get("phase5_diagnostics"))
    zero_trade = _mapping_or_empty(phase5.get("zero_trade_diagnostics"))
    diagnostics = _mapping_or_empty(zero_trade.get("strategy_diagnostics"))
    selected = diagnostics.get(str(strategy))
    return _mapping_or_empty(selected)


def _decision_directional_snapshot(
    *,
    analysis: object | None,
    candidate: object,
) -> dict[str, object]:
    """Capture existing decision-time directional evidence for calibration only."""

    payload = _analysis_payload(analysis)
    candidate_context = _mapping_or_empty(_jsonable(candidate))
    environment = _mapping_or_empty(payload.get("market_environment"))
    regime_by_timeframe = _mapping_or_empty(payload.get("regime_by_timeframe"))
    phase5 = _mapping_or_empty(payload.get("phase5_diagnostics"))
    zero_trade = _mapping_or_empty(phase5.get("zero_trade_diagnostics"))
    breakout_routing = _mapping_or_empty(zero_trade.get("breakout_routing"))

    strategy = (
        _directional_value(candidate_context, "strategy")
        or _directional_value(candidate_context, "candidate_id")
        or ""
    )
    if isinstance(strategy, str) and ":" in strategy:
        strategy = strategy.split(":", maxsplit=1)[0]

    strategy_diagnostics = _strategy_signal_diagnostics(
        payload=payload,
        strategy=strategy,
    )

    direction = _directional_value(candidate_context, "direction")
    if direction is None:
        candidate_id = _directional_value(candidate_context, "candidate_id")
        if isinstance(candidate_id, str):
            parts = candidate_id.split(":")
            direction = parts[1] if len(parts) > 1 else None

    long_score = _directional_value(
        environment,
        "long_suitability_score",
        "long_score",
    )
    short_score = _directional_value(
        environment,
        "short_suitability_score",
        "short_score",
    )
    long_numeric = (
        float(long_score)
        if isinstance(long_score, int | float) and not isinstance(long_score, bool)
        else None
    )
    short_numeric = (
        float(short_score)
        if isinstance(short_score, int | float) and not isinstance(short_score, bool)
        else None
    )

    direction_text = str(direction).lower() if direction is not None else ""
    chosen_advantage = None
    if long_numeric is not None and short_numeric is not None:
        if direction_text == "long":
            chosen_advantage = long_numeric - short_numeric
        elif direction_text == "short":
            chosen_advantage = short_numeric - long_numeric

    rejection_codes = strategy_diagnostics.get("rejection_codes")
    reasons = strategy_diagnostics.get("reasons")
    reason_codes = environment.get("reason_codes")

    return {
        "snapshot_schema_version": 3,
        "primary_regime": _directional_value(
            environment,
            "primary_regime",
            "regime",
        ),
        "higher_timeframe_bias": _directional_value(
            environment,
            "higher_timeframe_bias",
            "htf_bias",
        ),
        "alignment_score": _directional_value(environment, "alignment_score"),
        "conflict_score": _directional_value(environment, "conflict_score"),
        "tradeable": _directional_value(environment, "tradeable"),
        "environment_reason_codes": (
            list(reason_codes) if isinstance(reason_codes, (list, tuple)) else []
        ),
        "long_evidence_score": long_numeric,
        "short_evidence_score": short_numeric,
        "chosen_direction_advantage": chosen_advantage,
        "strategy_rejection_codes": (
            list(rejection_codes) if isinstance(rejection_codes, (list, tuple)) else []
        ),
        "strategy_rejection_reasons": (list(reasons) if isinstance(reasons, (list, tuple)) else []),
        "momentum_mismatch": (
            isinstance(rejection_codes, (list, tuple)) and "momentum_mismatch" in rejection_codes
        ),
        "higher_timeframe_contradiction": (
            isinstance(rejection_codes, (list, tuple))
            and "higher_timeframe_contradiction" in rejection_codes
        ),
        "direction_authority_opposed_count": breakout_routing.get(
            "direction_authority_opposed_count"
        ),
        "setup_authority_opposed_count": breakout_routing.get("setup_authority_opposed_count"),
        "execution_authority_opposed_count": breakout_routing.get(
            "execution_authority_opposed_count"
        ),
        "timing_frame_direction_violation_count": breakout_routing.get(
            "timing_frame_direction_violation_count"
        ),
        "timeframes": {
            str(timeframe): {"regime": _enum_value(regime)}
            for timeframe, regime in regime_by_timeframe.items()
        },
    }


def _ranking_diagnostics(
    record: CandidateRankingRecord,
    *,
    entry: float,
    stop: float,
    target: float,
    analysis: object | None = None,
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
        "diagnostic_schema_version": 2,
        "directional_snapshot": _decision_directional_snapshot(
            analysis=analysis,
            candidate=combined,
        ),
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


def _geometry_audit_diagnostics(
    audit: Mapping[str, object],
    *,
    analysis: object | None = None,
) -> dict[str, object]:
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
        "diagnostic_schema_version": 3,
        "directional_snapshot": _decision_directional_snapshot(
            analysis=analysis,
            candidate=diagnostic_values,
        ),
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
        "execution_cost_profile": _recursive_lookup(diagnostic_values, ("execution_cost_profile",)),
        "cost_profile_reason": _recursive_lookup(diagnostic_values, ("cost_profile_reason",)),
        "expected_cost_pct": _recursive_lookup(diagnostic_values, ("expected_cost_pct",)),
        "observed_spread_pct": _recursive_lookup(diagnostic_values, ("observed_spread_pct",)),
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
                analysis=analysis,
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
            item = _geometry_audit_diagnostics(
                audit,
                analysis=analysis,
            )
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


def _unique_geometry_population(
    calibration_records: list[dict[str, object]],
) -> dict[str, object]:
    """Summarize raw candidates by unique time/direction/trade geometry.

    This is research-only attribution. It does not alter ranking, replay, or
    production decisions.
    """

    def number(value: object) -> float | None:
        if isinstance(value, bool) or not isinstance(value, int | float):
            return None
        numeric = float(value)
        return round(numeric, 12) if math.isfinite(numeric) else None

    groups: dict[tuple[object, ...], dict[str, object]] = {}
    raw_candidate_count = 0

    for record in calibration_records:
        decision_time = record.get("decision_time")
        symbol = record.get("symbol")
        candidates = record.get("candidate_diagnostics")
        if not isinstance(candidates, list):
            continue

        for candidate in candidates:
            if not isinstance(candidate, Mapping):
                continue
            geometry = candidate.get("geometry_audit")
            if not isinstance(geometry, Mapping):
                continue

            candidate_id = candidate.get("candidate_id")
            strategy = candidate.get("strategy")
            identity = candidate_id.split(":") if isinstance(candidate_id, str) else []
            direction = identity[1] if len(identity) >= 2 else candidate.get("direction")
            lane = candidate.get("geometry_lane")
            state = candidate.get("geometry_state")
            rejection_codes = candidate.get("geometry_rejection_codes")

            key = (
                symbol,
                decision_time,
                direction,
                number(geometry.get("selected_entry")),
                number(geometry.get("entry_zone_low")),
                number(geometry.get("entry_zone_high")),
                number(geometry.get("executable_stop")),
                number(geometry.get("tp1_price")),
                lane,
            )
            raw_candidate_count += 1
            group = groups.setdefault(
                key,
                {
                    "symbol": symbol,
                    "decision_time": decision_time,
                    "direction": direction,
                    "selected_entry": key[3],
                    "entry_zone_low": key[4],
                    "entry_zone_high": key[5],
                    "executable_stop": key[6],
                    "tp1_price": key[7],
                    "geometry_lane": lane,
                    "candidate_ids": [],
                    "strategy_aliases": [],
                    "states": [],
                    "rejection_codes": [],
                    "minimum_viable_tp1_price": number(geometry.get("minimum_viable_tp1_price")),
                    "minimum_viable_tp1_distance": number(
                        geometry.get("minimum_viable_tp1_distance")
                    ),
                    "minimum_viable_tp1_distance_atr": number(
                        geometry.get("minimum_viable_tp1_distance_atr")
                    ),
                    "available_tp1_distance": number(geometry.get("available_tp1_distance")),
                    "available_tp1_distance_atr": number(
                        geometry.get("available_tp1_distance_atr")
                    ),
                    "tp1_feasibility_gap": number(geometry.get("tp1_feasibility_gap")),
                    "tp1_feasibility_gap_atr": number(geometry.get("tp1_feasibility_gap_atr")),
                    "geometry_feasible_before_quality": geometry.get(
                        "geometry_feasible_before_quality"
                    ),
                    "feasible_existing_target_count": geometry.get(
                        "feasible_existing_target_count"
                    ),
                    "nearest_feasible_existing_target_price": number(
                        geometry.get("nearest_feasible_existing_target_price")
                    ),
                    "nearest_feasible_existing_target_index": geometry.get(
                        "nearest_feasible_existing_target_index"
                    ),
                    "no_feasible_target_reason": geometry.get("no_feasible_target_reason"),
                },
            )

            if isinstance(candidate_id, str):
                ids = group["candidate_ids"]
                if isinstance(ids, list) and candidate_id not in ids:
                    ids.append(candidate_id)
            if isinstance(strategy, str):
                aliases = group["strategy_aliases"]
                if isinstance(aliases, list) and strategy not in aliases:
                    aliases.append(strategy)
            if isinstance(state, str):
                states = group["states"]
                if isinstance(states, list) and state not in states:
                    states.append(state)
            if isinstance(rejection_codes, list):
                codes = group["rejection_codes"]
                if isinstance(codes, list):
                    for code in rejection_codes:
                        if isinstance(code, str) and code not in codes:
                            codes.append(code)

    rejection_distribution: dict[str, int] = {}
    exclusive_rejection_distribution: dict[str, int] = {}
    duplicate_group_count = 0
    duplicate_candidate_count = 0
    rejected_unique_count = 0
    passed_unique_count = 0
    multi_gate_rejection_count = 0
    feasibility_counts = {
        "current_tp1_infeasible_but_farther_existing_target_feasible": 0,
        "no_existing_target_feasible": 0,
        "minimum_viable_tp1_beyond_lane_horizon": 0,
        "cost_only_infeasibility": 0,
        "target_type_only_infeasibility": 0,
    }
    serialized_groups: list[dict[str, object]] = []

    for group in groups.values():
        aliases = group["strategy_aliases"]
        ids = group["candidate_ids"]
        states = group["states"]
        codes = group["rejection_codes"]
        if isinstance(aliases, list):
            aliases.sort()
        if isinstance(ids, list):
            ids.sort()
        if isinstance(states, list):
            states.sort()
        if isinstance(codes, list):
            codes.sort()

        candidate_count = len(ids) if isinstance(ids, list) else 0
        duplicate_count = max(0, candidate_count - 1)
        if duplicate_count:
            duplicate_group_count += 1
            duplicate_candidate_count += duplicate_count

        rejected = (isinstance(states, list) and "reject" in states) or (
            isinstance(codes, list) and bool(codes)
        )
        if rejected:
            rejected_unique_count += 1
        else:
            passed_unique_count += 1

        current_gap = group.get("tp1_feasibility_gap")
        nearest_index = group.get("nearest_feasible_existing_target_index")
        feasible_before_quality = group.get("geometry_feasible_before_quality")
        no_feasible_reason = group.get("no_feasible_target_reason")
        if (
            isinstance(current_gap, int | float)
            and not isinstance(current_gap, bool)
            and float(current_gap) > 1e-9
            and isinstance(nearest_index, int)
            and not isinstance(nearest_index, bool)
            and nearest_index > 1
        ):
            feasibility_counts["current_tp1_infeasible_but_farther_existing_target_feasible"] += 1
        if feasible_before_quality is False:
            feasibility_counts["no_existing_target_feasible"] += 1
        if isinstance(no_feasible_reason, str) and no_feasible_reason in feasibility_counts:
            feasibility_counts[no_feasible_reason] += 1

        if isinstance(codes, list):
            for code in codes:
                rejection_distribution[code] = rejection_distribution.get(code, 0) + 1
            if len(codes) == 1:
                code = codes[0]
                exclusive_rejection_distribution[code] = (
                    exclusive_rejection_distribution.get(code, 0) + 1
                )
            elif len(codes) > 1:
                multi_gate_rejection_count += 1

        serialized_groups.append(
            {
                **group,
                "candidate_count": candidate_count,
                "duplicate_candidate_count": duplicate_count,
                "is_duplicate_geometry": duplicate_count > 0,
                "rejected": rejected,
            }
        )

    def sort_entry(item: Mapping[str, object]) -> float:
        value = item.get("selected_entry")
        if isinstance(value, bool) or not isinstance(value, int | float):
            return 0.0
        return float(value)

    serialized_groups.sort(
        key=lambda item: (
            str(item.get("decision_time") or ""),
            str(item.get("symbol") or ""),
            str(item.get("direction") or ""),
            sort_entry(item),
        )
    )

    return {
        "diagnostic_version": 1,
        "raw_candidate_count": raw_candidate_count,
        "unique_geometry_count": len(serialized_groups),
        "duplicate_group_count": duplicate_group_count,
        "duplicate_candidate_count": duplicate_candidate_count,
        "rejected_unique_geometry_count": rejected_unique_count,
        "passed_unique_geometry_count": passed_unique_count,
        "multi_gate_rejection_count": multi_gate_rejection_count,
        "unique_rejection_distribution": dict(sorted(rejection_distribution.items())),
        "exclusive_rejection_distribution": dict(sorted(exclusive_rejection_distribution.items())),
        "tp1_feasibility": feasibility_counts,
        "groups": serialized_groups,
        "production_behavior_changed": False,
    }


def _replay_class_from_source(source: object) -> str:
    if source == "production":
        return "production"
    if source == "conditional_portfolio":
        return "conditional"
    if source == "opportunity_portfolio":
        return "opportunity"
    if source in {"runner_plan", "geometry_rejected", "methodology_shadow"}:
        return "shadow"
    return "unknown"


def _canonical_source(source: object) -> bool:
    return source in {"production", "conditional_portfolio"}


def _sorted_replay_signals(
    signals: list[BacktestSignal],
) -> tuple[BacktestSignal, ...]:
    """Match the immutable request identity and suppress exact duplicate rows."""

    unique: dict[tuple[object, ...], BacktestSignal] = {}
    for signal in signals:
        identity = _replay_signal_sort_identity(signal)
        unique.setdefault(identity, signal)
    return tuple(unique[key] for key in sorted(unique))


def _replay_signal_sort_identity(signal: BacktestSignal) -> tuple[object, ...]:
    base: tuple[object, ...] = (
        signal.generated_at,
        signal.symbol,
        signal.replay_source,
    )
    if signal.candidate_id is not None:
        return (*base, "candidate", signal.candidate_id)
    return (
        *base,
        "geometry",
        signal.strategy.value,
        signal.direction.value,
        signal.entry_zone_low,
        signal.entry_price,
        signal.entry_zone_high,
        signal.stop_price,
        signal.target_prices,
        signal.partial_close_percentages,
        None if signal.activation_type is None else signal.activation_type.value,
        signal.activation_level,
        signal.pre_entry_invalidation_price,
        signal.maximum_chase_price,
        signal.activation_expiry_candles,
    )


def _evaluation_outcome_rows(payload: Mapping[str, object]) -> list[dict[str, object]]:
    """Expose research JSONL-shaped rows without treating rule scores as probabilities."""

    calibration_records = payload.get("calibration_records")
    profile_by_time: dict[str, Mapping[str, object]] = {}
    if isinstance(calibration_records, list):
        for item in calibration_records:
            if not isinstance(item, Mapping):
                continue
            decision_time = item.get("decision_time")
            market_profile = item.get("market_profile")
            if isinstance(decision_time, str) and isinstance(market_profile, Mapping):
                profile_by_time[decision_time] = market_profile

    study = payload.get("study")
    study_config_hash = study.get("config_hash") if isinstance(study, Mapping) else None
    configuration_id = (
        f"{payload.get('configuration_id')}:{study_config_hash}"
        if payload.get("configuration_id") and study_config_hash
        else str(payload.get("configuration_id") or study_config_hash or "unknown")
    )
    replay_timeframe = str(payload.get("replay_timeframe") or "unknown")
    symbol = str(payload.get("symbol") or "unknown")
    rows: list[dict[str, object]] = []
    sections: tuple[tuple[str, str], ...] = (
        ("trades", "canonical"),
        ("conditional_replay", "conditional"),
        ("opportunity_replay", "opportunity"),
        ("shadow_replay", "shadow"),
    )
    canonical_trade_times: set[str] = set()
    for section, geometry_profile in sections:
        section_value = payload.get(section)
        trades = (
            section_value
            if isinstance(section_value, list)
            else section_value.get("trades")
            if isinstance(section_value, Mapping)
            else None
        )
        if not isinstance(trades, list):
            continue
        for trade in trades:
            if not isinstance(trade, Mapping):
                continue
            metadata = trade.get("metadata")
            if not isinstance(metadata, Mapping) or metadata.get("entry_filled") is not True:
                continue
            signal = trade.get("signal")
            decision_time = trade.get("decision_time")
            profile = (
                profile_by_time.get(decision_time, {}) if isinstance(decision_time, str) else {}
            )
            realized_r = trade.get("realized_r_multiple")
            if isinstance(realized_r, bool) or not isinstance(realized_r, int | float):
                continue
            rows.append(
                {
                    "configuration_id": configuration_id,
                    "timestamp": decision_time,
                    "symbol": symbol,
                    "cohort": str(profile.get("cohort") or "unknown"),
                    "net_return_r": float(realized_r),
                    "strategy_family": (
                        str(signal.get("strategy") or "unknown")
                        if isinstance(signal, Mapping)
                        else "unknown"
                    ),
                    "timeframe": replay_timeframe,
                    "geometry_profile": geometry_profile,
                    "evaluation_population": ("canonical" if section == "trades" else "shadow"),
                    "executed": True,
                    "decision_state": str(trade.get("outcome") or "executed"),
                    "probability": None,
                    "label": None,
                    "probability_authority": ("unavailable_rule_score_is_not_a_probability"),
                }
            )
            if section == "trades" and isinstance(decision_time, str):
                canonical_trade_times.add(decision_time)
    if isinstance(calibration_records, list):
        for item in calibration_records:
            if not isinstance(item, Mapping):
                continue
            decision_time = item.get("decision_time")
            if not isinstance(decision_time, str) or decision_time in canonical_trade_times:
                continue
            no_trade_profile = item.get("market_profile")
            rows.append(
                {
                    "configuration_id": configuration_id,
                    "timestamp": decision_time,
                    "symbol": symbol,
                    "cohort": (
                        str(no_trade_profile.get("cohort") or "unknown")
                        if isinstance(no_trade_profile, Mapping)
                        else "unknown"
                    ),
                    "net_return_r": 0.0,
                    "strategy_family": "no_trade",
                    "timeframe": replay_timeframe,
                    "geometry_profile": "canonical",
                    "evaluation_population": "canonical",
                    "executed": False,
                    "decision_state": "no_trade",
                    "probability": None,
                    "label": None,
                    "probability_authority": ("unavailable_rule_score_is_not_a_probability"),
                }
            )
    return rows


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
    calibration_by_candidate = {
        str(record.get("candidate_id")): record
        for record in calibration_records
        if isinstance(record.get("candidate_id"), str) and str(record.get("candidate_id")).strip()
    }
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
        candidate_id = signal.get("candidate_id") if isinstance(signal, Mapping) else None
        calibration = (
            calibration_by_candidate.get(str(candidate_id), {})
            if isinstance(candidate_id, str) and candidate_id.strip()
            else {}
        )
        if not calibration:
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
                "strategy_version": (
                    signal.get("strategy_version")
                    if isinstance(signal, Mapping)
                    else calibration.get("strategy_version")
                ),
                "setup_methodology_version": (
                    signal.get("setup_methodology_version")
                    if isinstance(signal, Mapping)
                    else calibration.get("setup_methodology_version")
                ),
                "setup_geometry_fingerprint": calibration.get("setup_geometry_fingerprint"),
                "replay_source": (
                    signal.get("replay_source") if isinstance(signal, Mapping) else None
                ),
                "replay_class": _replay_class_from_source(
                    signal.get("replay_source") if isinstance(signal, Mapping) else None
                ),
                "canonical_portfolio": (
                    calibration.get("canonical_portfolio")
                    if isinstance(calibration.get("canonical_portfolio"), bool)
                    else _canonical_source(
                        signal.get("replay_source") if isinstance(signal, Mapping) else None
                    )
                ),
                "targets_hit": target_count,
                "maximum_favorable_excursion_r": metadata_map.get("maximum_favorable_excursion_r"),
                "maximum_adverse_excursion_r": metadata_map.get("maximum_adverse_excursion_r"),
                "counterfactual_path_mfe_r": metadata_map.get("counterfactual_path_mfe_r"),
                "counterfactual_path_mae_r": metadata_map.get("counterfactual_path_mae_r"),
                "direction_correct_at_horizon": metadata_map.get("direction_correct_at_horizon"),
                "thesis_outcome": metadata_map.get("thesis_outcome"),
                "target_before_invalidation": metadata_map.get("target_before_invalidation"),
                "invalidation_before_target": metadata_map.get("invalidation_before_target"),
                "partial_directional_success": metadata_map.get("partial_directional_success"),
                "late_reentry_available": metadata_map.get("late_reentry_available"),
                "late_reentry_first_candle": metadata_map.get("late_reentry_first_candle"),
                "thesis_evaluation_horizon_candles": metadata_map.get(
                    "thesis_evaluation_horizon_candles"
                ),
                "thesis_first_target_candle": metadata_map.get("thesis_first_target_candle"),
                "thesis_first_invalidation_candle": metadata_map.get(
                    "thesis_first_invalidation_candle"
                ),
                "entry_follow_through": metadata_map.get("entry_follow_through"),
                "same_candle_stop_target_ambiguous": metadata_map.get(
                    "same_candle_stop_target_ambiguous"
                ),
                "target_touched": metadata_map.get("target_touched"),
                "net_profitable_target": metadata_map.get("net_profitable_target"),
                "stop_breach_classification": metadata_map.get("post_stop_classification"),
                "stop_breach_depth_r": metadata_map.get(
                    "post_stop_maximum_excursion_beyond_stop_r"
                ),
                "maximum_close_beyond_stop_r": metadata_map.get(
                    "post_stop_maximum_close_beyond_stop_r"
                ),
                "bars_traded_beyond_stop": metadata_map.get("post_stop_bars_traded_beyond_stop"),
                "bars_closed_beyond_stop": metadata_map.get("post_stop_bars_closed_beyond_stop"),
                "consecutive_closes_beyond_stop": metadata_map.get(
                    "post_stop_max_consecutive_closes_beyond_stop"
                ),
                "bars_to_stop_reclaim": metadata_map.get("post_stop_bars_to_stop_reclaim"),
                "bars_to_entry_reclaim": metadata_map.get("post_stop_bars_to_reclaim"),
                "shallow_stop_sweep": metadata_map.get("shallow_stop_sweep"),
                "moderate_stop_breach": metadata_map.get("moderate_stop_breach"),
                "deep_directional_failure": metadata_map.get("deep_directional_failure"),
                "later_recovery_after_directional_failure": metadata_map.get(
                    "later_recovery_after_directional_failure"
                ),
                "wick_only_stop_sweep": metadata_map.get("wick_only_stop_sweep"),
                "sweep_reclaim_candidate": metadata_map.get("sweep_reclaim_candidate"),
                "sweep_reclaim_confirmed": metadata_map.get("sweep_reclaim_confirmed"),
                "sweep_reclaim_rejected_reason": metadata_map.get("sweep_reclaim_rejected_reason"),
                "reclaim_candle_body_ratio": metadata_map.get("reclaim_candle_body_ratio"),
                "reclaim_close_location": metadata_map.get("reclaim_close_location"),
                "entry_level_reclaimed": metadata_map.get("entry_level_reclaimed"),
                "entry_level_held_next_candle": metadata_map.get("entry_level_held_next_candle"),
                "retest_available": metadata_map.get("retest_available"),
                "retest_held": metadata_map.get("retest_held"),
                "remaining_target_room_r": metadata_map.get("remaining_target_room_r"),
                "recovery_entry_authorized": metadata_map.get("recovery_entry_authorized"),
                "recovery_entry_price": metadata_map.get("recovery_entry_price"),
                "recovery_entry_candle": metadata_map.get("recovery_entry_candle"),
                "recovery_reclaim_time": metadata_map.get("recovery_reclaim_time"),
                "recovery_event_id": metadata_map.get("recovery_event_id"),
                "recovery_target_before_failure": metadata_map.get(
                    "recovery_target_before_failure"
                ),
                "aggressive_reclaim_entry_available": metadata_map.get(
                    "aggressive_reclaim_entry_available"
                ),
                "aggressive_reclaim_entry_price": metadata_map.get(
                    "aggressive_reclaim_entry_price"
                ),
                "aggressive_reclaim_stop_price": metadata_map.get("aggressive_reclaim_stop_price"),
                "aggressive_reclaim_target_price": metadata_map.get(
                    "aggressive_reclaim_target_price"
                ),
                "aggressive_reclaim_outcome": metadata_map.get("aggressive_reclaim_outcome"),
                "aggressive_reclaim_gross_r": metadata_map.get("aggressive_reclaim_gross_r"),
                "aggressive_reclaim_net_r": metadata_map.get("aggressive_reclaim_net_r"),
                "aggressive_reclaim_bars_to_outcome": metadata_map.get(
                    "aggressive_reclaim_bars_to_outcome"
                ),
                "aggressive_reclaim_target_before_stop": metadata_map.get(
                    "aggressive_reclaim_target_before_stop"
                ),
                "retest_recovery_entry_available": metadata_map.get(
                    "retest_recovery_entry_available"
                ),
                "retest_recovery_entry_price": metadata_map.get("retest_recovery_entry_price"),
                "retest_recovery_stop_price": metadata_map.get("retest_recovery_stop_price"),
                "retest_recovery_target_price": metadata_map.get("retest_recovery_target_price"),
                "retest_recovery_outcome": metadata_map.get("retest_recovery_outcome"),
                "retest_recovery_gross_r": metadata_map.get("retest_recovery_gross_r"),
                "retest_recovery_net_r": metadata_map.get("retest_recovery_net_r"),
                "retest_recovery_bars_to_outcome": metadata_map.get(
                    "retest_recovery_bars_to_outcome"
                ),
                "retest_recovery_target_before_stop": metadata_map.get(
                    "retest_recovery_target_before_stop"
                ),
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

    event_groups: dict[str, list[dict[str, object]]] = {}
    for record in records:
        event_id = record.get("recovery_event_id")
        if (
            record.get("aggressive_reclaim_entry_available") is True
            and isinstance(event_id, str)
            and event_id
        ):
            event_groups.setdefault(event_id, []).append(record)

    for members in event_groups.values():

        def event_rank_key(item: dict[str, object]) -> tuple[float, str, str]:
            raw_net_r = item.get("aggressive_reclaim_net_r")
            net_r = (
                float(raw_net_r)
                if isinstance(raw_net_r, int | float) and not isinstance(raw_net_r, bool)
                else 0.0
            )
            return (
                -net_r,
                str(item.get("decision_time") or ""),
                str(item.get("opportunity_id") or ""),
            )

        ranked = sorted(members, key=event_rank_key)
        member_count = len(ranked)
        for rank, record in enumerate(ranked, start=1):
            record["recovery_event_member_count"] = member_count
            record["recovery_event_rank"] = rank
            record["recovery_event_duplicate"] = rank > 1
            record["recovery_event_selected"] = rank == 1

    return records


def _filled_or_legacy_execution_trades(trades: object) -> tuple[object, ...]:
    # Return explicit fills, with a legacy fallback only when fill flags are absent.
    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    explicit = _filled_execution_trades(values)
    has_explicit_fill_metadata = any(
        isinstance(getattr(trade, "metadata", None), Mapping) and "entry_filled" in trade.metadata
        for trade in values
    )
    if has_explicit_fill_metadata:
        return explicit
    return tuple(
        trade
        for trade in values
        if getattr(getattr(trade, "outcome", None), "value", None) in {"target", "stop", "expired"}
        and isinstance(getattr(trade, "metadata", None), Mapping)
    )


def _outcome_distribution(trades: object) -> dict[str, object]:
    """Report lifecycle and post-fill outcomes with their correct populations."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    filled_values: tuple[object, ...] = _filled_execution_trades(values)
    explicit_fill_metadata = any(
        isinstance(getattr(trade, "metadata", None), Mapping) and "entry_filled" in trade.metadata
        for trade in values
    )
    if not explicit_fill_metadata:
        filled_values = tuple(
            trade
            for trade in values
            if getattr(getattr(trade, "outcome", None), "value", None)
            in {"target", "stop", "expired"}
            and isinstance(getattr(trade, "metadata", None), Mapping)
        )
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

    for trade in filled_values:
        metadata = getattr(trade, "metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        target_count = int(metadata.get("partial_target_count", 0) or 0)
        for threshold, key in (
            (1, "tp1_hit_count"),
            (2, "tp2_hit_count"),
            (3, "tp3_hit_count"),
        ):
            if target_count >= threshold:
                target_counts[key] += 1
        ambiguity_count += metadata.get("same_candle_stop_target_ambiguous") is True
        profitable_target_count += metadata.get("net_profitable_target") is True

    lifecycle_total = len(values)
    filled_total = len(filled_values)
    return {
        **outcome_counts,
        **target_counts,
        "signal_outcome_count": lifecycle_total,
        "filled_trade_count": filled_total,
        "net_profitable_target_count": profitable_target_count,
        "same_candle_stop_target_ambiguity_count": ambiguity_count,
        "stop_rate": outcome_counts["stop"] / filled_total if filled_total else None,
        "missed_entry_rate": (
            outcome_counts["missed_entry"] / lifecycle_total if lifecycle_total else None
        ),
        "pre_entry_invalidation_rate": (
            outcome_counts["pre_entry_invalidated"] / lifecycle_total if lifecycle_total else None
        ),
        "activation_expiry_rate": (
            outcome_counts["activation_expired"] / lifecycle_total if lifecycle_total else None
        ),
        "expired_rate": (outcome_counts["expired"] / filled_total if filled_total else None),
        "tp1_hit_rate": (target_counts["tp1_hit_count"] / filled_total if filled_total else None),
        "tp2_hit_rate": (target_counts["tp2_hit_count"] / filled_total if filled_total else None),
        "tp3_hit_rate": (target_counts["tp3_hit_count"] / filled_total if filled_total else None),
    }


def _filled_execution_trades(trades: object) -> tuple[SimulatedTrade, ...]:
    """Return records that represent actual historical entry fills."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    return tuple(
        trade
        for trade in values
        if isinstance(trade, SimulatedTrade)
        and isinstance(trade.metadata, Mapping)
        and trade.metadata.get("entry_filled") is True
    )


def _execution_metrics(trades: object) -> dict[str, object]:
    """Return fill-only performance without counting unfilled plans as trades."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    filled = _filled_execution_trades(values)
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
    """Describe unique chronological decisions through the setup funnel.

    Production decisions have precedence. Conditional replay is counted as a
    future setup only when the same decision timestamp has no production setup.
    This prevents alternative replay lanes from inflating coverage above 100%.
    """

    production_values = tuple(
        trade
        for trade in (
            tuple(production_trades) if isinstance(production_trades, tuple | list) else ()
        )
        if isinstance(trade, SimulatedTrade)
    )
    conditional_values = tuple(
        trade
        for trade in (
            tuple(conditional_trades) if isinstance(conditional_trades, tuple | list) else ()
        )
        if isinstance(trade, SimulatedTrade)
    )
    production_times = {trade.signal.generated_at.isoformat() for trade in production_values}
    conditional_times = {trade.signal.generated_at.isoformat() for trade in conditional_values}
    future_only_times = conditional_times - production_times
    overlap_times = production_times & conditional_times

    production_fill_times = {
        trade.signal.generated_at.isoformat()
        for trade in production_values
        if trade.metadata.get("entry_filled") is True
    }
    conditional_fill_times = {
        trade.signal.generated_at.isoformat()
        for trade in conditional_values
        if trade.metadata.get("entry_filled") is True
        and trade.signal.generated_at.isoformat() in future_only_times
    }

    true_no_setup = 0
    pending_activation_count = 0
    for decision in no_trade_decisions:
        reasons = decision.get("reasons")
        reason_values = reasons if isinstance(reasons, list | tuple) else ()
        if "canonical_opportunity_pending_activation" in reason_values:
            pending_activation_count += 1
        else:
            true_no_setup += 1

    immediate_count = len(production_times)
    future_count = max(len(future_only_times), pending_activation_count)
    setup_count = min(decision_point_count, immediate_count + future_count)
    return {
        "decision_point_count": decision_point_count,
        "raw_immediate_signal_count": production_signals,
        "raw_conditional_signal_count": conditional_signals,
        "pending_activation_decision_count": pending_activation_count,
        "overlapping_setup_decision_count": len(overlap_times),
        "immediate_setup_count": immediate_count,
        "future_setup_count": future_count,
        "setup_found_count": setup_count,
        "true_no_setup_count": true_no_setup,
        "immediate_setup_rate": (
            immediate_count / decision_point_count if decision_point_count else None
        ),
        "future_setup_rate": (
            future_count / decision_point_count if decision_point_count else None
        ),
        "setup_coverage_rate": (
            setup_count / decision_point_count if decision_point_count else None
        ),
        "immediate_fill_count": len(production_fill_times),
        "future_fill_count": len(conditional_fill_times),
        "total_fill_count": len(production_fill_times | conditional_fill_times),
    }


def _risk_and_excursion(trades: object) -> dict[str, object]:
    """Separate realised fill excursion from counterfactual plan-path evidence."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    filled_values = _filled_or_legacy_execution_trades(values)
    mfe_values: list[float] = []
    mae_values: list[float] = []
    path_mfe_values: list[float] = []
    path_mae_values: list[float] = []

    for trade in filled_values:
        metadata = getattr(trade, "metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        mfe = metadata.get("maximum_favorable_excursion_r")
        mae = metadata.get("maximum_adverse_excursion_r")
        if isinstance(mfe, int | float) and not isinstance(mfe, bool):
            mfe_values.append(float(mfe))
        if isinstance(mae, int | float) and not isinstance(mae, bool):
            mae_values.append(float(mae))

    for trade in values:
        metadata = getattr(trade, "metadata", {})
        if not isinstance(metadata, Mapping):
            continue
        path_mfe = metadata.get("counterfactual_path_mfe_r")
        path_mae = metadata.get("counterfactual_path_mae_r")
        if isinstance(path_mfe, int | float) and not isinstance(path_mfe, bool):
            path_mfe_values.append(float(path_mfe))
        if isinstance(path_mae, int | float) and not isinstance(path_mae, bool):
            path_mae_values.append(float(path_mae))

    return {
        "filled_trade_count": len(filled_values),
        "average_mfe_r": sum(mfe_values) / len(mfe_values) if mfe_values else None,
        "average_mae_r": sum(mae_values) / len(mae_values) if mae_values else None,
        "best_mfe_r": max(mfe_values) if mfe_values else None,
        "worst_mae_r": max(mae_values) if mae_values else None,
        "counterfactual_path_count": max(len(path_mfe_values), len(path_mae_values)),
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


def _thesis_metrics(trades: object) -> dict[str, object]:
    """Aggregate prediction quality independently from activation and fill quality."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    counts = {
        "thesis_correct": 0,
        "thesis_partially_correct": 0,
        "thesis_wrong": 0,
        "thesis_unresolved": 0,
    }
    late_reentry = 0
    target_before_invalidation = 0
    invalidation_before_target = 0

    for trade in values:
        metadata = getattr(trade, "metadata", None)
        if not isinstance(metadata, Mapping):
            continue
        outcome = metadata.get("thesis_outcome")
        if isinstance(outcome, str) and outcome in counts:
            counts[outcome] += 1
        late_reentry += metadata.get("late_reentry_available") is True
        target_before_invalidation += metadata.get("target_before_invalidation") is True
        invalidation_before_target += metadata.get("invalidation_before_target") is True

    evaluable = counts["thesis_correct"] + counts["thesis_wrong"]
    directional_evaluable = evaluable + counts["thesis_partially_correct"]
    total = sum(counts.values())
    return {
        **counts,
        "total_thesis_records": total,
        "strict_evaluable_count": evaluable,
        "strict_thesis_accuracy": (counts["thesis_correct"] / evaluable if evaluable else None),
        "directional_evaluable_count": directional_evaluable,
        "directional_success_rate": (
            (counts["thesis_correct"] + counts["thesis_partially_correct"]) / directional_evaluable
            if directional_evaluable
            else None
        ),
        "target_before_invalidation_count": target_before_invalidation,
        "invalidation_before_target_count": invalidation_before_target,
        "late_reentry_available_count": late_reentry,
        "late_reentry_available_rate": late_reentry / total if total else None,
        "diagnostic_only": True,
        "production_behavior_changed": False,
    }


def _stop_breach_metrics(trades: object) -> dict[str, object]:
    """Aggregate diagnostic post-stop severity without changing trade outcomes."""

    values = tuple(trades) if isinstance(trades, tuple | list) else ()
    counts: dict[str, int] = {}
    stop_count = 0
    shallow = 0
    moderate = 0
    deep = 0
    later_recovery_after_failure = 0
    breach_depths: list[float] = []
    close_depths: list[float] = []

    for trade in values:
        metadata = getattr(trade, "metadata", None)
        if not isinstance(metadata, Mapping) or metadata.get("stop_hit") is not True:
            continue
        stop_count += 1
        classification = metadata.get("post_stop_classification")
        if isinstance(classification, str):
            counts[classification] = counts.get(classification, 0) + 1
        shallow += metadata.get("shallow_stop_sweep") is True
        moderate += metadata.get("moderate_stop_breach") is True
        deep += metadata.get("deep_directional_failure") is True
        later_recovery_after_failure += (
            metadata.get("later_recovery_after_directional_failure") is True
        )
        depth = metadata.get("post_stop_maximum_excursion_beyond_stop_r")
        if isinstance(depth, int | float) and not isinstance(depth, bool):
            breach_depths.append(float(depth))
        close_depth = metadata.get("post_stop_maximum_close_beyond_stop_r")
        if isinstance(close_depth, int | float) and not isinstance(close_depth, bool):
            close_depths.append(float(close_depth))

    return {
        "stop_count": stop_count,
        "classification_counts": counts,
        "shallow_stop_sweep_count": shallow,
        "moderate_stop_breach_count": moderate,
        "deep_directional_failure_count": deep,
        "later_recovery_after_directional_failure_count": (later_recovery_after_failure),
        "deep_directional_failure_rate": deep / stop_count if stop_count else None,
        "average_stop_breach_depth_r": (
            sum(breach_depths) / len(breach_depths) if breach_depths else None
        ),
        "maximum_stop_breach_depth_r": max(breach_depths) if breach_depths else None,
        "average_close_beyond_stop_r": (
            sum(close_depths) / len(close_depths) if close_depths else None
        ),
        "diagnostic_only": True,
        "production_behavior_changed": False,
    }


def _sweep_reclaim_metrics(trades: object) -> dict[str, object]:
    """Aggregate diagnostic sweep-reclaim and Part 2E robustness evidence."""

    minimum_net_r_gate = 0.30
    values = tuple(trades) if isinstance(trades, tuple | list) else ()

    def numeric(metadata: Mapping[str, object], key: str) -> float | None:
        value = metadata.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return float(value)
        return None

    def representative(members: list[SimulatedTrade]) -> SimulatedTrade:
        # Never select an event member using realized outcome or net R.
        return min(
            members,
            key=lambda item: (
                item.signal.generated_at,
                item.signal.candidate_id or "",
                item.signal.strategy.value,
            ),
        )

    def speed_name(bars: object) -> str | None:
        if not isinstance(bars, int | float) or isinstance(bars, bool):
            return None
        if bars <= 3:
            return "fast"
        if bars <= 8:
            return "normal"
        return "slow"

    def mode_summary(
        selected: list[SimulatedTrade],
        *,
        prefix: str,
    ) -> dict[str, object]:
        outcomes = {"target": 0, "stop": 0, "expired": 0}
        net_values: list[float] = []
        target_reached = 0
        positive_net = 0
        gate_passed = 0
        ambiguity_count = 0
        speed: dict[str, dict[str, object]] = {
            name: {
                "event_count": 0,
                "target_count": 0,
                "stop_count": 0,
                "expired_count": 0,
                "target_reached_count": 0,
                "positive_net_count": 0,
                "net_r_gate_pass_count": 0,
                "same_candle_ambiguity_count": 0,
                "total_net_r": 0.0,
                "average_net_r": None,
            }
            for name in ("fast", "normal", "slow")
        }

        for trade in selected:
            metadata = getattr(trade, "metadata", {})
            if not isinstance(metadata, Mapping):
                continue
            outcome = metadata.get(f"{prefix}_outcome")
            if isinstance(outcome, str) and outcome in outcomes:
                outcomes[outcome] += 1
            net_r = numeric(metadata, f"{prefix}_net_r")
            reached = metadata.get(f"{prefix}_target_reached") is True or outcome == "target"
            positive = metadata.get(f"{prefix}_positive_net") is True or (
                net_r is not None and net_r > 0.0
            )
            passed = metadata.get(f"{prefix}_net_r_gate_passed") is True or (
                net_r is not None and net_r >= minimum_net_r_gate
            )
            ambiguous = metadata.get(f"{prefix}_same_candle_ambiguous") is True
            target_reached += reached
            positive_net += positive
            gate_passed += passed
            ambiguity_count += ambiguous
            if net_r is not None:
                net_values.append(net_r)

            bucket = speed_name(metadata.get(f"{prefix}_bars_to_outcome"))
            if bucket is None:
                continue
            group = speed[bucket]
            event_count = group.get("event_count")
            if not isinstance(event_count, int) or isinstance(event_count, bool):
                event_count = 0
            group["event_count"] = event_count + 1

            if outcome in outcomes:
                key = f"{outcome}_count"
                outcome_count = group.get(key)
                if not isinstance(outcome_count, int) or isinstance(outcome_count, bool):
                    outcome_count = 0
                group[key] = outcome_count + 1

            target_reached_count = group.get("target_reached_count")
            if not isinstance(target_reached_count, int) or isinstance(target_reached_count, bool):
                target_reached_count = 0
            group["target_reached_count"] = target_reached_count + int(reached)

            positive_net_count = group.get("positive_net_count")
            if not isinstance(positive_net_count, int) or isinstance(positive_net_count, bool):
                positive_net_count = 0
            group["positive_net_count"] = positive_net_count + int(positive)

            gate_pass_count = group.get("net_r_gate_pass_count")
            if not isinstance(gate_pass_count, int) or isinstance(gate_pass_count, bool):
                gate_pass_count = 0
            group["net_r_gate_pass_count"] = gate_pass_count + int(passed)

            ambiguity_total = group.get("same_candle_ambiguity_count")
            if not isinstance(ambiguity_total, int) or isinstance(ambiguity_total, bool):
                ambiguity_total = 0
            group["same_candle_ambiguity_count"] = ambiguity_total + int(ambiguous)

            if net_r is not None:
                total_net_r = group.get("total_net_r")
                if not isinstance(total_net_r, int | float) or isinstance(total_net_r, bool):
                    total_net_r = 0.0
                group["total_net_r"] = float(total_net_r) + net_r

        for group in speed.values():
            event_count = group.get("event_count")
            count = (
                event_count
                if isinstance(event_count, int) and not isinstance(event_count, bool)
                else 0
            )
            total_net_r = group.get("total_net_r")
            total = (
                float(total_net_r)
                if isinstance(total_net_r, int | float) and not isinstance(total_net_r, bool)
                else 0.0
            )
            group["average_net_r"] = total / count if count else None

        count = len(selected)
        return {
            "event_count": count,
            "target_count": outcomes["target"],
            "stop_count": outcomes["stop"],
            "expired_count": outcomes["expired"],
            "target_rate": outcomes["target"] / count if count else None,
            "target_reached_count": target_reached,
            "target_reached_rate": target_reached / count if count else None,
            "positive_net_count": positive_net,
            "positive_net_rate": positive_net / count if count else None,
            "minimum_net_r_gate": minimum_net_r_gate,
            "net_r_gate_pass_count": gate_passed,
            "net_r_gate_pass_rate": gate_passed / count if count else None,
            "same_candle_ambiguity_count": ambiguity_count,
            "average_net_r": sum(net_values) / len(net_values) if net_values else None,
            "total_net_r": sum(net_values),
            "speed_performance": speed,
            "speed_counts": {
                name: (
                    value
                    if isinstance((value := group.get("event_count")), int)
                    and not isinstance(value, bool)
                    else 0
                )
                for name, group in speed.items()
            },
        }

    candidates = 0
    confirmed = 0
    authorized = 0
    retests = 0
    retests_held = 0
    targets_before_failure = 0
    rejected: dict[str, int] = {}
    paired_counts = {
        "both_available": 0,
        "aggressive_only": 0,
        "retest_only": 0,
        "neither_available": 0,
    }
    aggressive_members: dict[str, list[SimulatedTrade]] = {}
    retest_members: dict[str, list[SimulatedTrade]] = {}
    strict_ids: set[str] = set()
    current_ids: set[str] = set()
    loose_ids: set[str] = set()
    episode_ids: set[str] = set()
    aggressive_raw = 0
    retest_raw = 0
    paired_available_count = 0
    paired_predicted_counts: dict[str, int] = {}
    paired_realized_counts: dict[str, int] = {}
    paired_prediction_evaluable_count = 0
    paired_prediction_correct_count = 0
    paired_directional_prediction_count = 0
    paired_directional_prediction_correct_count = 0
    paired_abstention_count = 0
    paired_abstention_correct_count = 0
    paired_overall_decision_count = 0
    paired_overall_decision_correct_count = 0
    paired_net_r_deltas: list[float] = []
    paired_false_aggressive_count = 0
    paired_false_retest_count = 0
    selector_raw_row_count = 0

    for trade in values:
        metadata = getattr(trade, "metadata", None)
        if not isinstance(metadata, Mapping):
            continue
        candidates += metadata.get("sweep_reclaim_candidate") is True
        confirmed += metadata.get("sweep_reclaim_confirmed") is True
        authorized += metadata.get("recovery_entry_authorized") is True
        retests += metadata.get("retest_available") is True
        retests_held += metadata.get("retest_held") is True
        targets_before_failure += metadata.get("recovery_target_before_failure") is True

        pair = metadata.get("recovery_entry_pair_classification")
        if not isinstance(pair, str) or pair not in paired_counts:
            aggressive = metadata.get("aggressive_reclaim_entry_available") is True
            retest = metadata.get("retest_recovery_entry_available") is True
            pair = (
                "both_available"
                if aggressive and retest
                else "aggressive_only"
                if aggressive
                else "retest_only"
                if retest
                else "neither_available"
            )
        paired_counts[pair] += 1

        if metadata.get("recovery_pair_available") is True:
            paired_available_count += 1
            predicted = metadata.get("recovery_pair_predicted_mode")
            if isinstance(predicted, str):
                paired_predicted_counts[predicted] = paired_predicted_counts.get(predicted, 0) + 1
            realized = metadata.get("recovery_pair_realized_winner")
            if isinstance(realized, str):
                paired_realized_counts[realized] = paired_realized_counts.get(realized, 0) + 1
            delta = numeric(metadata, "recovery_pair_net_r_delta")
            if delta is not None:
                paired_net_r_deltas.append(delta)
            correct = metadata.get("recovery_pair_prediction_correct") is True
            directional_evaluable = (
                metadata.get("recovery_pair_directional_prediction_evaluable") is True
            )
            abstention = metadata.get("recovery_pair_abstention") is True
            abstention_correct = metadata.get("recovery_pair_abstention_correct") is True
            overall_evaluable = directional_evaluable or abstention

            if predicted in {"prefer_aggressive", "prefer_retest"} and realized in {
                "aggressive",
                "retest",
            }:
                paired_prediction_evaluable_count += 1
                paired_prediction_correct_count += int(correct)

            paired_directional_prediction_count += int(directional_evaluable)
            paired_directional_prediction_correct_count += int(directional_evaluable and correct)
            paired_abstention_count += int(abstention)
            paired_abstention_correct_count += int(abstention and abstention_correct)
            paired_overall_decision_count += int(overall_evaluable)
            paired_overall_decision_correct_count += int(overall_evaluable and correct)

            paired_false_aggressive_count += int(
                predicted == "prefer_aggressive" and realized == "retest"
            )
            paired_false_retest_count += int(
                predicted == "prefer_retest" and realized == "aggressive"
            )

            selector_raw_row_count += 1

        for key, destination in (
            ("recovery_event_id_strict", strict_ids),
            ("recovery_event_id", current_ids),
            ("recovery_event_id_loose", loose_ids),
            ("recovery_market_episode_id", episode_ids),
        ):
            value = metadata.get(key)
            if isinstance(value, str) and value:
                destination.add(value)

        event_id = metadata.get("recovery_event_id")
        if metadata.get("aggressive_reclaim_entry_available") is True:
            aggressive_raw += 1
            if isinstance(event_id, str) and event_id:
                aggressive_members.setdefault(event_id, []).append(trade)
        if metadata.get("retest_recovery_entry_available") is True:
            retest_raw += 1
            if isinstance(event_id, str) and event_id:
                retest_members.setdefault(event_id, []).append(trade)

        reason = metadata.get("sweep_reclaim_rejected_reason")
        if isinstance(reason, str) and reason != "none":
            rejected[reason] = rejected.get(reason, 0) + 1

    unique_aggressive = [representative(members) for members in aggressive_members.values()]
    unique_retest = [representative(members) for members in retest_members.values()]

    selector_event_ids = set(aggressive_members).intersection(retest_members)
    selector_representatives = [
        representative(aggressive_members[event_id]) for event_id in selector_event_ids
    ]
    selector_outcome_counts: dict[str, int] = {}
    selector_realized_counts: dict[str, int] = {}
    selector_evaluable_count = 0
    selector_correct_count = 0
    selector_failure_to_abstain_count = 0
    selector_less_bad_selection_count = 0
    aggressive_projection_errors: list[float] = []
    retest_projection_errors: list[float] = []
    aggressive_projection_absolute_errors: list[float] = []
    retest_projection_absolute_errors: list[float] = []
    aggressive_projection_over_count = 0
    retest_projection_over_count = 0
    aggressive_projection_under_count = 0
    retest_projection_under_count = 0

    for selector_trade in selector_representatives:
        selector_metadata = getattr(selector_trade, "metadata", {})
        selector_outcome = selector_metadata.get("recovery_selector_outcome")
        if isinstance(selector_outcome, str):
            selector_outcome_counts[selector_outcome] = (
                selector_outcome_counts.get(selector_outcome, 0) + 1
            )
        selector_realized = selector_metadata.get("recovery_selector_realized_classification")
        if isinstance(selector_realized, str):
            selector_realized_counts[selector_realized] = (
                selector_realized_counts.get(selector_realized, 0) + 1
            )
        selector_evaluable = selector_metadata.get("recovery_selector_evaluable") is True
        selector_correct = selector_metadata.get("recovery_selector_correct") is True
        selector_evaluable_count += int(selector_evaluable)
        selector_correct_count += int(selector_evaluable and selector_correct)
        selector_failure_to_abstain_count += int(
            selector_outcome in {"select_aggressive", "select_retest"}
            and selector_realized in {"both_negative", "both_below_gate"}
        )
        selector_less_bad_selection_count += int(
            selector_outcome in {"select_aggressive", "select_retest"}
            and selector_realized == "both_negative"
        )

        aggressive_projected = numeric(
            selector_metadata,
            "recovery_pair_aggressive_projected_net_r",
        )
        aggressive_realized = numeric(
            selector_metadata,
            "aggressive_reclaim_net_r",
        )
        if aggressive_projected is not None and aggressive_realized is not None:
            aggressive_error = aggressive_projected - aggressive_realized
            aggressive_projection_errors.append(aggressive_error)
            aggressive_projection_absolute_errors.append(abs(aggressive_error))
            aggressive_projection_over_count += int(aggressive_error > 0.0)
            aggressive_projection_under_count += int(aggressive_error < 0.0)

        retest_projected = numeric(
            selector_metadata,
            "recovery_pair_retest_projected_net_r",
        )
        retest_realized = numeric(
            selector_metadata,
            "retest_recovery_net_r",
        )
        if retest_projected is not None and retest_realized is not None:
            retest_error = retest_projected - retest_realized
            retest_projection_errors.append(retest_error)
            retest_projection_absolute_errors.append(abs(retest_error))
            retest_projection_over_count += int(retest_error > 0.0)
            retest_projection_under_count += int(retest_error < 0.0)
    aggressive_summary = mode_summary(
        unique_aggressive,
        prefix="aggressive_reclaim",
    )
    retest_summary = mode_summary(
        unique_retest,
        prefix="retest_recovery",
    )

    aggressive_metrics: dict[str, object] = {
        "available_count": aggressive_raw,
        "raw_entry_count": aggressive_raw,
        "unique_event_count": len(unique_aggressive),
        "duplicate_entry_count": aggressive_raw - len(unique_aggressive),
        "target_count": sum(
            getattr(trade, "metadata", {}).get("aggressive_reclaim_outcome") == "target"
            for trade in values
        ),
        "stop_count": sum(
            getattr(trade, "metadata", {}).get("aggressive_reclaim_outcome") == "stop"
            for trade in values
        ),
        "expired_count": sum(
            getattr(trade, "metadata", {}).get("aggressive_reclaim_outcome") == "expired"
            for trade in values
        ),
        "target_rate": (
            sum(
                getattr(trade, "metadata", {}).get("aggressive_reclaim_outcome") == "target"
                for trade in values
            )
            / aggressive_raw
            if aggressive_raw
            else None
        ),
        "unique_target_count": aggressive_summary["target_count"],
        "unique_stop_count": aggressive_summary["stop_count"],
        "unique_expired_count": aggressive_summary["expired_count"],
        "unique_target_rate": aggressive_summary["target_rate"],
        "unique_target_reached_count": aggressive_summary["target_reached_count"],
        "unique_positive_net_count": aggressive_summary["positive_net_count"],
        "unique_minimum_net_r_gate": minimum_net_r_gate,
        "unique_minimum_net_r_gate_pass_count": aggressive_summary["net_r_gate_pass_count"],
        "unique_minimum_net_r_gate_pass_rate": aggressive_summary["net_r_gate_pass_rate"],
        "unique_same_candle_ambiguity_count": aggressive_summary["same_candle_ambiguity_count"],
        "unique_average_net_r": aggressive_summary["average_net_r"],
        "unique_total_net_r": aggressive_summary["total_net_r"],
        "unique_speed_counts": aggressive_summary["speed_counts"],
        "unique_speed_performance": aggressive_summary["speed_performance"],
    }

    retest_metrics: dict[str, object] = {
        "available_count": retest_raw,
        "raw_entry_count": retest_raw,
        "unique_event_count": len(unique_retest),
        "duplicate_entry_count": retest_raw - len(unique_retest),
        "target_count": sum(
            getattr(trade, "metadata", {}).get("retest_recovery_outcome") == "target"
            for trade in values
        ),
        "stop_count": sum(
            getattr(trade, "metadata", {}).get("retest_recovery_outcome") == "stop"
            for trade in values
        ),
        "expired_count": sum(
            getattr(trade, "metadata", {}).get("retest_recovery_outcome") == "expired"
            for trade in values
        ),
        "target_rate": (
            sum(
                getattr(trade, "metadata", {}).get("retest_recovery_outcome") == "target"
                for trade in values
            )
            / retest_raw
            if retest_raw
            else None
        ),
        "unique_target_count": retest_summary["target_count"],
        "unique_stop_count": retest_summary["stop_count"],
        "unique_expired_count": retest_summary["expired_count"],
        "unique_target_rate": retest_summary["target_rate"],
        "unique_target_reached_count": retest_summary["target_reached_count"],
        "unique_positive_net_count": retest_summary["positive_net_count"],
        "unique_minimum_net_r_gate": minimum_net_r_gate,
        "unique_minimum_net_r_gate_pass_count": retest_summary["net_r_gate_pass_count"],
        "unique_minimum_net_r_gate_pass_rate": retest_summary["net_r_gate_pass_rate"],
        "unique_same_candle_ambiguity_count": retest_summary["same_candle_ambiguity_count"],
        "unique_average_net_r": retest_summary["average_net_r"],
        "unique_total_net_r": retest_summary["total_net_r"],
        "unique_speed_counts": retest_summary["speed_counts"],
        "unique_speed_performance": retest_summary["speed_performance"],
    }

    both_event_ids = set(aggressive_members).intersection(retest_members)
    paired_net_differences: list[float] = []
    aggressive_better = 0
    retest_better = 0
    tied = 0
    for event_id in both_event_ids:
        aggressive_trade = representative(aggressive_members[event_id])
        retest_trade = representative(retest_members[event_id])
        aggressive_metadata = getattr(aggressive_trade, "metadata", {})
        retest_metadata = getattr(retest_trade, "metadata", {})
        aggressive_net = numeric(aggressive_metadata, "aggressive_reclaim_net_r")
        retest_net = numeric(retest_metadata, "retest_recovery_net_r")
        if aggressive_net is None or retest_net is None:
            continue
        difference = aggressive_net - retest_net
        paired_net_differences.append(difference)
        if difference > 0.0:
            aggressive_better += 1
        elif difference < 0.0:
            retest_better += 1
        else:
            tied += 1

    current_count = len(current_ids)
    return {
        "candidate_count": candidates,
        "confirmed_count": confirmed,
        "authorized_count": authorized,
        "candidate_rate": candidates / len(values) if values else None,
        "confirmation_rate": confirmed / candidates if candidates else None,
        "authorization_rate": authorized / candidates if candidates else None,
        "retest_available_count": retests,
        "retest_held_count": retests_held,
        "recovery_target_before_failure_count": targets_before_failure,
        "aggressive_reclaim": aggressive_metrics,
        "retest_recovery": retest_metrics,
        "paired_entry_comparison": {
            "classification_counts": paired_counts,
            "availability_counts": paired_counts,
            "paired_available_count": paired_available_count,
            "both_available_unique_event_count": paired_available_count,
            "comparable_net_r_count": len(paired_net_r_deltas),
            "predicted_mode_counts": paired_predicted_counts,
            "realized_winner_counts": paired_realized_counts,
            "prediction_evaluable_count": paired_prediction_evaluable_count,
            "prediction_correct_count": paired_prediction_correct_count,
            "prediction_accuracy": (
                paired_prediction_correct_count / paired_prediction_evaluable_count
                if paired_prediction_evaluable_count
                else None
            ),
            "directional_prediction_count": paired_directional_prediction_count,
            "directional_prediction_correct_count": (paired_directional_prediction_correct_count),
            "directional_prediction_accuracy": (
                paired_directional_prediction_correct_count / paired_directional_prediction_count
                if paired_directional_prediction_count
                else None
            ),
            "abstention_count": paired_abstention_count,
            "abstention_correct_count": paired_abstention_correct_count,
            "abstention_accuracy": (
                paired_abstention_correct_count / paired_abstention_count
                if paired_abstention_count
                else None
            ),
            "overall_decision_count": paired_overall_decision_count,
            "overall_decision_correct_count": (paired_overall_decision_correct_count),
            "overall_decision_accuracy": (
                paired_overall_decision_correct_count / paired_overall_decision_count
                if paired_overall_decision_count
                else None
            ),
            "false_aggressive_selection_count": paired_false_aggressive_count,
            "false_retest_selection_count": paired_false_retest_count,
            "selector_raw_row_count": selector_raw_row_count,
            "selector_unique_event_count": len(selector_representatives),
            "selector_duplicate_row_count": (
                selector_raw_row_count - len(selector_representatives)
            ),
            "selector_outcome_counts": selector_outcome_counts,
            "selector_realized_classification_counts": selector_realized_counts,
            "selector_evaluable_count": selector_evaluable_count,
            "selector_correct_count": selector_correct_count,
            "selector_accuracy": (
                selector_correct_count / selector_evaluable_count
                if selector_evaluable_count
                else None
            ),
            "selector_failure_to_abstain_count": (selector_failure_to_abstain_count),
            "selector_less_bad_selection_count": (selector_less_bad_selection_count),
            "selector_basis": "absolute_viability_then_relative_preference",
            "projection_calibration": {
                "aggressive_count": len(aggressive_projection_errors),
                "aggressive_average_error_r": (
                    sum(aggressive_projection_errors) / len(aggressive_projection_errors)
                    if aggressive_projection_errors
                    else None
                ),
                "aggressive_mean_absolute_error_r": (
                    sum(aggressive_projection_absolute_errors)
                    / len(aggressive_projection_absolute_errors)
                    if aggressive_projection_absolute_errors
                    else None
                ),
                "aggressive_overprediction_count": aggressive_projection_over_count,
                "aggressive_underprediction_count": aggressive_projection_under_count,
                "aggressive_overprediction_rate": (
                    aggressive_projection_over_count / len(aggressive_projection_errors)
                    if aggressive_projection_errors
                    else None
                ),
                "retest_count": len(retest_projection_errors),
                "retest_average_error_r": (
                    sum(retest_projection_errors) / len(retest_projection_errors)
                    if retest_projection_errors
                    else None
                ),
                "retest_mean_absolute_error_r": (
                    sum(retest_projection_absolute_errors) / len(retest_projection_absolute_errors)
                    if retest_projection_absolute_errors
                    else None
                ),
                "retest_overprediction_count": retest_projection_over_count,
                "retest_underprediction_count": retest_projection_under_count,
                "retest_overprediction_rate": (
                    retest_projection_over_count / len(retest_projection_errors)
                    if retest_projection_errors
                    else None
                ),
                "diagnostic_only": True,
                "production_behavior_changed": False,
            },
            "average_aggressive_minus_retest_net_r": (
                sum(paired_net_r_deltas) / len(paired_net_r_deltas) if paired_net_r_deltas else None
            ),
            "total_aggressive_minus_retest_net_r": sum(paired_net_r_deltas),
            "comparison_basis": "entry_time_geometry_pre_outcome",
        },
        "event_identity_sensitivity": {
            "strict_unique_event_count": len(strict_ids),
            "current_unique_event_count": current_count,
            "loose_unique_event_count": len(loose_ids),
            "strict_minus_current": len(strict_ids) - current_count,
            "current_minus_loose": current_count - len(loose_ids),
            "market_episode_count": len(episode_ids),
            "current_events_per_market_episode": (
                current_count / len(episode_ids) if episode_ids else None
            ),
        },
        "rejected_reason_counts": rejected,
        "diagnostic_only": True,
        "production_behavior_changed": False,
        "representative_selection_basis": "earliest_generated_signal_pre_outcome",
    }


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
