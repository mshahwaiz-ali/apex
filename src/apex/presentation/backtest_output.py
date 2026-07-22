"""Readable chronological backtest and research-campaign reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    UNAVAILABLE,
    format_percentage,
    format_ratio,
    render_fields,
    render_section,
    render_title,
)


def render_backtest(payload: Mapping[str, object]) -> str:
    """Render a single-symbol chronological replay report."""

    metrics = _mapping(payload.get("metrics"))
    execution_metrics = _mapping(payload.get("execution_metrics"))
    decision_funnel = _mapping(payload.get("decision_funnel"))
    promotion = _mapping(payload.get("promotion_statistics"))
    study = _mapping(payload.get("study"))
    outcomes = _mapping(payload.get("outcome_distribution"))
    excursions = _mapping(payload.get("risk_and_excursion"))
    assumptions = _mapping(payload.get("execution_assumptions"))
    partitions = _mapping(payload.get("metrics_by_partition"))
    trade_records = _sequence(payload.get("trades"))
    no_trade_records = _sequence(payload.get("no_trade_decisions"))
    conditional = _mapping(payload.get("conditional_replay"))
    conditional_activation = _mapping(conditional.get("activation_metrics"))
    conditional_execution = _mapping(conditional.get("execution_metrics"))
    conditional_outcomes = _mapping(conditional.get("outcome_distribution"))
    shadow = _mapping(payload.get("shadow_replay"))
    shadow_metrics = _mapping(shadow.get("metrics"))
    shadow_accuracy = _mapping(shadow.get("direction_accuracy"))
    shadow_excursions = _mapping(shadow.get("risk_and_excursion"))
    symbol = str(payload.get("symbol") or "Unknown market")
    trades = _number(metrics.get("total_trades"))
    expectancy = _number(metrics.get("expectancy"))
    verdict = _verdict(trades, expectancy)
    sections = [
        render_title(f"Apex Backtest • {symbol}"),
        render_section(
            "Verdict",
            "\n".join(
                (
                    f"▶  {verdict}",
                    render_fields(
                        (
                            ("Replay timeframe", payload.get("replay_timeframe")),
                            ("Decision points", payload.get("decision_point_count")),
                            ("Signals generated", payload.get("generated_signal_count")),
                            ("Trades executed", metrics.get("total_trades")),
                            ("No-trade decisions", payload.get("no_trade_decision_count")),
                        )
                    ),
                )
            ),
        ),
        render_section(
            "Test configuration",
            render_fields(
                (
                    ("Replay timeframe", payload.get("replay_timeframe")),
                    ("Replay candles", payload.get("replay_candles")),
                    ("Decision points", payload.get("decision_point_count")),
                    ("Methodology gate", assumptions.get("methodology_gate_mode")),
                    ("Fee", _pct_value(assumptions.get("fee_pct"))),
                    ("Slippage", _pct_value(assumptions.get("slippage_pct"))),
                    ("Funding", _pct_value(assumptions.get("funding_pct"))),
                    ("Holding window", assumptions.get("maximum_holding_candles")),
                )
            ),
        ),
        render_section(
            "Decision funnel",
            render_fields(
                (
                    ("Decision points", decision_funnel.get("decision_point_count")),
                    ("Immediate setups", decision_funnel.get("immediate_setup_count")),
                    ("Future setups", decision_funnel.get("future_setup_count")),
                    ("True no-setup decisions", decision_funnel.get("true_no_setup_count")),
                    (
                        "Setup coverage",
                        format_percentage(
                            decision_funnel.get("setup_coverage_rate"),
                            ratio=True,
                        ),
                    ),
                    ("Immediate fills", decision_funnel.get("immediate_fill_count")),
                    ("Future fills", decision_funnel.get("future_fill_count")),
                )
            ),
        ),
        render_section(
            "Executed-trade performance",
            render_fields(
                (
                    ("Filled trades", execution_metrics.get("filled_trade_count")),
                    (
                        "Fill rate",
                        format_percentage(execution_metrics.get("fill_rate"), ratio=True),
                    ),
                    (
                        "Win rate",
                        format_percentage(execution_metrics.get("win_rate"), ratio=True),
                    ),
                    ("Expectancy", _r(_number(execution_metrics.get("expectancy")))),
                    ("Net P&L", _signed(execution_metrics.get("net_profit"))),
                    ("Profit factor", format_ratio(execution_metrics.get("profit_factor"))),
                    ("Maximum drawdown", _signed(execution_metrics.get("maximum_drawdown"))),
                )
            ),
        ),
        render_section(
            "Performance after modeled costs — all production signal outcomes",
            render_fields(
                (
                    ("Win rate", format_percentage(metrics.get("win_rate"), ratio=True)),
                    ("Expectancy", _r(expectancy)),
                    ("Net P&L", _signed(metrics.get("net_profit"))),
                    ("Profit factor", format_ratio(metrics.get("profit_factor"))),
                    ("Average win", _signed(metrics.get("average_win"))),
                    ("Average loss", _signed(metrics.get("average_loss"))),
                    ("Maximum drawdown", _signed(metrics.get("maximum_drawdown"))),
                )
            ),
        ),
        render_section(
            "Outcome distribution",
            render_fields(
                (
                    ("Target exits", outcomes.get("target")),
                    ("Stop exits", outcomes.get("stop")),
                    ("Expired setups", outcomes.get("expired")),
                    ("Missed entries", outcomes.get("missed_entry")),
                    ("TP1 hit rate", format_percentage(outcomes.get("tp1_hit_rate"), ratio=True)),
                    ("TP2 hit rate", format_percentage(outcomes.get("tp2_hit_rate"), ratio=True)),
                    ("TP3 hit rate", format_percentage(outcomes.get("tp3_hit_rate"), ratio=True)),
                    ("Stop rate", format_percentage(outcomes.get("stop_rate"), ratio=True)),
                )
            ),
        ),
        render_section(
            "Risk and excursion",
            render_fields(
                (
                    ("Average MFE", _r(_number(excursions.get("average_mfe_r")))),
                    ("Average MAE", _r(_number(excursions.get("average_mae_r")))),
                    ("Best MFE", _r(_number(excursions.get("best_mfe_r")))),
                    ("Worst MAE", _r(_number(excursions.get("worst_mae_r")))),
                )
            ),
        ),
        render_section("Partition performance", _render_partitions(partitions)),
        render_section(
            "Trade record",
            _render_trades(trade_records) if trade_records else "No executed trades.",
        ),
        render_section(
            "No-trade decisions",
            _render_no_trades(no_trade_records) if no_trade_records else "None.",
        ),
        render_section(
            "Conditional replay (diagnostic only)",
            render_fields(
                (
                    ("Future setups", conditional_activation.get("future_setup_count")),
                    ("Activated", conditional_activation.get("activation_count")),
                    (
                        "Activation rate",
                        format_percentage(
                            conditional_activation.get("activation_rate"),
                            ratio=True,
                        ),
                    ),
                    ("Filled", conditional_activation.get("fill_count")),
                    (
                        "Fill rate",
                        format_percentage(
                            conditional_activation.get("fill_rate"),
                            ratio=True,
                        ),
                    ),
                    (
                        "Average activation wait",
                        conditional_activation.get("average_activation_wait_candles"),
                    ),
                    ("Targets", conditional_outcomes.get("target")),
                    ("Stops", conditional_outcomes.get("stop")),
                    ("Pre-entry invalidations", conditional_outcomes.get("pre_entry_invalidated")),
                    ("Activation expiries", conditional_outcomes.get("activation_expired")),
                    ("Missed entries", conditional_outcomes.get("missed_entry")),
                    (
                        "Executed win rate",
                        format_percentage(
                            conditional_execution.get("win_rate"),
                            ratio=True,
                        ),
                    ),
                    (
                        "Executed expectancy",
                        _r(_number(conditional_execution.get("expectancy"))),
                    ),
                )
            ),
        ),
        render_section(
            "Candidate shadow replay (diagnostic only)",
            render_fields(
                (
                    ("Candidate signals", shadow.get("signal_count")),
                    ("Resolved outcomes", shadow_metrics.get("total_trades")),
                    (
                        "Direction accuracy",
                        format_percentage(shadow_accuracy.get("accuracy"), ratio=True),
                    ),
                    (
                        "Forward-path MFE",
                        _r(_number(shadow_excursions.get("average_counterfactual_path_mfe_r"))),
                    ),
                    (
                        "Forward-path MAE",
                        _r(_number(shadow_excursions.get("average_counterfactual_path_mae_r"))),
                    ),
                    ("Source mix", _join_mapping(shadow.get("source_distribution"))),
                )
            ),
        ),
        render_section(
            "Robustness checks",
            render_fields(
                (
                    ("Calibration authority", "Not promoted"),
                    (
                        "Deflated Sharpe probability",
                        format_percentage(promotion.get("deflated_sharpe_probability"), ratio=True),
                    ),
                    (
                        "Backtest overfitting risk",
                        format_percentage(
                            promotion.get("probability_backtest_overfitting"), ratio=True
                        ),
                    ),
                    ("Skipped signals", study.get("skipped_signal_count")),
                    ("Dataset fingerprint", _short_hash(study.get("dataset_hash"))),
                )
            ),
        ),
    ]
    return "\n\n".join(sections)


def _render_partitions(partitions: Mapping[str, object]) -> str:
    blocks: list[str] = []
    for key, label in (
        ("training", "Training"),
        ("validation", "Validation"),
        ("final_test", "Final test"),
    ):
        metrics = _mapping(partitions.get(key))
        blocks.append(
            "\n".join(
                (
                    label,
                    render_fields(
                        (
                            ("Trades", metrics.get("total_trades")),
                            ("Win rate", format_percentage(metrics.get("win_rate"), ratio=True)),
                            ("Expectancy", _r(_number(metrics.get("expectancy")))),
                            ("Profit factor", format_ratio(metrics.get("profit_factor"))),
                            ("Drawdown", _signed(metrics.get("maximum_drawdown"))),
                        )
                    ),
                )
            )
        )
    return "\n\n".join(blocks)


def _render_trades(trades: Sequence[object]) -> str:
    blocks: list[str] = []
    for trade in trades:
        item = _mapping(trade)
        signal = _mapping(item.get("signal"))
        blocks.append(
            "\n".join(
                (
                    f"Trade {item.get('trade_number', '?')} — "
                    f"{signal.get('symbol', UNAVAILABLE)} "
                    f"{str(signal.get('direction') or '').upper()}",
                    render_fields(
                        (
                            ("Decision time", item.get("decision_time")),
                            ("Opportunity", item.get("opportunity_id")),
                            ("Sequence", item.get("sequence_role")),
                            ("Actionability", item.get("actionability_state")),
                            ("Strategy", signal.get("strategy")),
                            ("Entry", signal.get("entry_price")),
                            ("Stop", signal.get("stop_price")),
                            ("Targets", _join(signal.get("target_prices"))),
                            ("Outcome", item.get("outcome")),
                            ("Realized R", _r(_number(item.get("realized_r_multiple")))),
                            ("Net P&L", _signed(item.get("net_pnl"))),
                            ("MFE", _r(_number(item.get("maximum_favorable_excursion_r")))),
                            ("MAE", _r(_number(item.get("maximum_adverse_excursion_r")))),
                            ("Partition", item.get("partition")),
                        )
                    ),
                )
            )
        )
    return "\n\n".join(blocks)


def _render_no_trades(decisions: Sequence[object]) -> str:
    lines: list[str] = []
    for decision in decisions:
        item = _mapping(decision)
        reasons = item.get("reasons")
        reason_text = (
            "; ".join(str(value) for value in reasons) if isinstance(reasons, list) else ""
        )
        lines.append(
            f"{item.get('decision_time', UNAVAILABLE)} — "
            f"{item.get('reason_code') or reason_text or 'No executable opportunity'}"
        )
    return "\n".join(lines)


def render_campaign(payload: Mapping[str, object]) -> str:
    """Render a complete public-data campaign status report."""

    month_values = [str(item) for item in _sequence(payload.get("months"))]
    universe = _mapping(payload.get("universe_by_month"))
    verified_files = _mapping(payload.get("verified_files"))
    missing_files = _mapping(payload.get("missing_files"))
    artifacts = _mapping(payload.get("artifacts"))
    missing_count = int(_number(payload.get("missing_file_count")) or 0)
    training = payload.get("model_training")
    status = "COMPLETE WITH MISSING DATA" if missing_count else "COMPLETE"

    return "\n\n".join(
        (
            render_title("Apex Historical Research Campaign"),
            render_section(
                "Campaign Configuration",
                "\n".join(
                    (
                        f"▶  {status}",
                        render_fields(
                            (
                                ("Campaign status", status.title()),
                                ("UTC range", _range(month_values)),
                                ("Complete months", len(month_values)),
                                ("Dataset root", payload.get("dataset_dir")),
                                ("Download verification", "Checksum-backed public archives"),
                                ("Calibration authority", "Withheld"),
                            )
                        ),
                    )
                ),
            ),
            render_section(
                "Dataset Coverage",
                render_fields(
                    (
                        ("Verified files", payload.get("verified_file_count")),
                        ("Missing files", payload.get("missing_file_count")),
                        ("Coverage state", "Incomplete" if missing_count else "Complete"),
                        ("File detail records", len(verified_files)),
                    )
                ),
            ),
            render_section(
                "Universe Summary",
                "\n".join(
                    (
                        render_fields(
                            (
                                ("Unique symbols", payload.get("symbol_count")),
                                ("Configured monthly cap", payload.get("universe_size")),
                                ("Universe source", payload.get("universe_path")),
                            )
                        ),
                        _render_monthly_universe(universe),
                    )
                ),
            ),
            render_section(
                "Missing Data",
                _render_mapping_lines(missing_files, empty="No missing campaign files."),
            ),
            render_section(
                "Manifest",
                render_fields(
                    (
                        ("Path", payload.get("manifest")),
                        ("Schema version", payload.get("manifest_schema_version")),
                        ("Fingerprint", _short_hash(payload.get("manifest_hash"))),
                    )
                ),
            ),
            render_section("Model Training", _render_training(training)),
            render_section(
                "Artifacts",
                render_fields(
                    (
                        (
                            "Dataset root",
                            artifacts.get("dataset_dir") or payload.get("dataset_dir"),
                        ),
                        ("Universe", artifacts.get("universe") or payload.get("universe_path")),
                        ("Manifest", artifacts.get("manifest") or payload.get("manifest")),
                        ("Probability authority", "Withheld until every promotion gate passes"),
                    )
                ),
            ),
        )
    )


def _render_monthly_universe(universe: Mapping[str, object]) -> str:
    if not universe:
        return "Monthly universe detail unavailable."
    lines: list[str] = []
    for month, symbols in sorted(universe.items()):
        lines.append(f"{month}: {len(_sequence(symbols))} symbols")
    return "\n".join(lines)


def _render_mapping_lines(
    values: Mapping[str, object],
    *,
    empty: str,
    limit: int = 20,
) -> str:
    if not values:
        return empty
    items = sorted(values.items())
    lines = [f"{key} — {value}" for key, value in items[:limit]]
    remaining = len(items) - limit
    if remaining > 0:
        lines.append(
            f"Showing {limit} of {len(items)} records; {remaining} more in JSON/report file."
        )
    return "\n".join(lines)


def _render_training(training: object) -> str:
    if training == "not requested":
        return render_fields(
            (
                ("Requested", "No"),
                ("Status", "Not requested"),
                ("Authority", "No profitability claim"),
            )
        )
    if isinstance(training, Mapping):
        return render_fields(
            (
                ("Requested", "Yes"),
                ("Status", training.get("status") or "Completed"),
                ("Artifacts", training.get("artifact_count")),
                ("Authority", "Subject to final promotion gates"),
            )
        )
    return render_fields(
        (
            ("Requested", "Yes"),
            ("Status", training),
            ("Authority", "Subject to final promotion gates"),
        )
    )


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> list[object]:
    return list(value) if isinstance(value, Sequence) and not isinstance(value, str | bytes) else []


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _r(value: float | None) -> str:
    return UNAVAILABLE if value is None else f"{value:+.3f}R"


def _signed(value: object) -> str:
    number = _number(value)
    return UNAVAILABLE if number is None else f"{number:+,.4f}"


def _pct_value(value: object) -> str:
    number = _number(value)
    return UNAVAILABLE if number is None else f"{number:.4f}%"


def _join(value: object) -> str:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return UNAVAILABLE
    return ", ".join(str(item) for item in value) or UNAVAILABLE


def _join_mapping(value: object) -> str:
    if not isinstance(value, Mapping) or not value:
        return UNAVAILABLE
    return ", ".join(f"{key}: {item}" for key, item in sorted(value.items()))


def _short_hash(value: object) -> str:
    text = str(value or "")
    return f"{text[:12]}…" if len(text) > 12 else text or UNAVAILABLE


def _range(months: Sequence[str]) -> str:
    if not months:
        return UNAVAILABLE
    return months[0] if len(months) == 1 else f"{months[0]} → {months[-1]}"


def _verdict(trades: float | None, expectancy: float | None) -> str:
    if not trades:
        return "INSUFFICIENT EXECUTED TRADES — NO PERFORMANCE CONCLUSION"
    if expectancy is None:
        return "RESULT AVAILABLE — EXPECTANCY UNAVAILABLE"
    if expectancy > 0:
        return "POSITIVE SAMPLE — NOT YET PROOF OF FUTURE PERFORMANCE"
    return "NEGATIVE SAMPLE — STRATEGY DID NOT SHOW AN EDGE"


__all__ = ["render_backtest", "render_campaign"]
