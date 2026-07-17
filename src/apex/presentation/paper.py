"""Professional terminal presentation for paper-trading operations."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    UNAVAILABLE,
    format_amount,
    format_percentage,
    format_price,
    format_ratio,
    humanize_code,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_paper_cycle(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one paper lifecycle cycle from its canonical payload."""

    normalize_output_mode(mode)
    cycle = _mapping(payload.get("cycle"))
    failures = _sequence(payload.get("provider_failures"))
    sections = [
        render_title("Paper Trading Cycle"),
        render_section(
            "Outcome",
            render_fields(
                (
                    ("Market", humanize_code(cycle.get("market_type"))),
                    ("Eligible trades", cycle.get("eligible_trade_count", 0)),
                    ("Advanced trades", cycle.get("advanced_trade_count", 0)),
                    ("Unchanged trades", cycle.get("unchanged_trade_count", 0)),
                    ("Provider failures", len(failures)),
                    ("Fully collected", _yes_no(payload.get("fully_collected"))),
                )
            ),
        ),
        render_section("Next action", _cycle_next_action(cycle, failures)),
    ]
    if failures:
        sections.append(render_section("Blocked symbols", render_bullets(_failure_lines(failures))))
    sections.append(
        render_section(
            "Persistence",
            render_fields(
                (
                    ("Cycle report", payload.get("cycle_report_path") or UNAVAILABLE),
                    ("Daily report", payload.get("daily_report_path") or UNAVAILABLE),
                )
            ),
        )
    )
    return "\n\n".join(sections)


def render_paper_pipeline(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one combined intake and lifecycle pipeline payload."""

    normalize_output_mode(mode)
    intake = _mapping(payload.get("intake"))
    cycle = _mapping(payload.get("cycle"))
    runtime = _mapping(cycle.get("runtime"))
    runtime_cycle = _mapping(runtime.get("cycle"))
    analytics = _mapping(payload.get("lifecycle_analytics"))
    diagnostics = _mapping(payload.get("diagnostics"))
    failures = _sequence(runtime.get("provider_failures"))
    sections = [
        render_title("Paper Trading Pipeline"),
        render_section(
            "Pipeline health",
            render_fields(
                (
                    ("Market", humanize_code(payload.get("market_type"))),
                    ("Outcome", humanize_code(payload.get("outcome") or "completed")),
                    ("Observed", intake.get("candidates_observed", 0)),
                    ("Accepted", intake.get("accepted", 0)),
                    ("Rejected", intake.get("rejected", 0)),
                    ("Duplicates", intake.get("duplicates_skipped", 0)),
                    ("Advanced", runtime_cycle.get("advanced_trade_count", 0)),
                    ("Unchanged", runtime_cycle.get("unchanged_trade_count", 0)),
                    ("Provider failures", len(failures)),
                )
            ),
        ),
        render_section(
            "Lifecycle evidence",
            render_fields(
                (
                    ("Waiting for entry", analytics.get("waiting_for_entry", 0)),
                    ("Entered trades", analytics.get("entered_trades", 0)),
                    ("Partial exits", analytics.get("partial_target_fills", 0)),
                    ("Completed targets", analytics.get("full_target_completions", 0)),
                    ("Stopped trades", analytics.get("stop_loss_exits", 0)),
                    ("Invalidated", analytics.get("invalidations", 0)),
                    ("Realized net PnL", format_amount(analytics.get("realized_net_pnl"))),
                    (
                        "Average realized R",
                        _r_multiple(analytics.get("average_realized_r_multiple")),
                    ),
                )
            ),
        ),
        render_section("Next action", _pipeline_next_action(intake, runtime_cycle, failures)),
    ]
    sections.append(
        render_section(
            "Pipeline diagnostics",
            render_fields(
                (
                    ("Scan analyses", diagnostics.get("scan_analysis_count", UNAVAILABLE)),
                    ("Scanner failures", diagnostics.get("scanner_failure_count", UNAVAILABLE)),
                    ("Run identifier", payload.get("run_id") or UNAVAILABLE),
                    ("Log path", payload.get("log_path") or UNAVAILABLE),
                )
            ),
        )
    )
    if failures:
        sections.append(
            render_section("Provider failures", render_bullets(_failure_lines(failures)))
        )
    return "\n\n".join(sections)


def render_paper_status(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render paper scheduler and operations readiness."""

    normalize_output_mode(mode)
    markets = _sequence(payload.get("markets"))
    sections = [
        render_title("Paper Trading Operations Status"),
        render_section(
            "Readiness",
            render_fields(
                (
                    ("Operations ready", _yes_no(payload.get("operations_ready"))),
                    ("Scheduler ready", _yes_no(payload.get("scheduler_ready"))),
                    ("Trades recorded", payload.get("total_trade_count", 0)),
                    ("Daily summaries", payload.get("daily_report_count", 0)),
                    ("Review reports", payload.get("review_report_count", 0)),
                )
            ),
        ),
        render_section(
            "Market status",
            render_bullets(_market_status_lines(markets) or (UNAVAILABLE,)),
        ),
        render_section("Next action", _status_next_action(payload, markets)),
    ]
    sections.append(
        render_section(
            "Operational diagnostics",
            render_bullets(_market_diagnostic_lines(markets) or (UNAVAILABLE,)),
        )
    )
    return "\n\n".join(sections)


def render_paper_report(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
    replay: bool = False,
) -> str:
    """Render paper performance, guidance, and replay reports."""

    normalize_output_mode(mode)
    performance = _mapping(payload.get("performance"))
    guidance = _mapping(payload.get("guidance"))
    trades = _sequence(guidance.get("trades"))
    title = "Paper Trading Replay Report" if replay else "Paper Trading Report"
    sections = [
        render_title(title),
        render_section(
            "Performance",
            render_fields(
                (
                    (
                        "Total trades",
                        performance.get("total_trades", payload.get("replayed_count", 0)),
                    ),
                    ("Open trades", performance.get("open_trades", UNAVAILABLE)),
                    ("Closed trades", performance.get("closed_trades", UNAVAILABLE)),
                    ("Net PnL", format_amount(performance.get("net_pnl"))),
                    ("Win rate", format_percentage(performance.get("win_rate"), ratio=True)),
                    ("Replay failures", payload.get("failure_count", UNAVAILABLE)),
                )
            ),
        ),
        render_section(
            "Operator guidance",
            render_bullets(_guidance_lines(trades) or ("No paper trades require action.",)),
        ),
    ]
    sections.append(
        render_section(
            "Trade details",
            render_bullets(_trade_detail_lines(trades) or (UNAVAILABLE,)),
        )
    )
    return "\n\n".join(sections)


def render_paper_trade(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one opened, rejected, updated, partial, or completed paper trade."""

    normalize_output_mode(mode)
    trade = _mapping(payload.get("trade"))
    signal = _mapping(trade.get("signal"))
    plan = _mapping(trade.get("futures_plan")) or _mapping(payload.get("futures_plan"))
    state = trade.get("state") or payload.get("state")
    reasons = _sequence(payload.get("reasons"))
    instruction = payload.get("instruction")
    next_action = (
        str(instruction)
        if instruction is not None
        else _trade_next_action(state, reasons)
    )
    sections = [
        render_title(
            f"Paper Trade — {signal.get('symbol') or payload.get('symbol') or UNAVAILABLE}"
        ),
        render_section(
            "Trade outcome",
            render_fields(
                (
                    (
                        "Result",
                        humanize_code(payload.get("result") or payload.get("status") or state),
                    ),
                    (
                        "Direction",
                        humanize_code(signal.get("direction") or payload.get("direction")),
                    ),
                    ("Lifecycle state", humanize_code(state)),
                    ("Operator action", humanize_code(payload.get("current_action"))),
                    (
                        "Trade identifier",
                        trade.get("trade_id") or payload.get("trade_id") or UNAVAILABLE,
                    ),
                )
            ),
        ),
        render_section(
            "Active plan",
            render_fields(
                (
                    ("Entry", format_price(_first(plan, signal, "entry_price", "ideal_entry"))),
                    ("Stop", format_price(_first(plan, signal, "stop_price", "stop_loss"))),
                    ("Leverage", _leverage(plan)),
                    ("Quantity", format_ratio(_first(plan, signal, "quantity"), decimals=6)),
                    (
                        "Margin",
                        format_amount(_first(plan, signal, "required_margin", "margin")),
                    ),
                    (
                        "Wallet exposure",
                        format_percentage(_first(plan, signal, "wallet_exposure_pct")),
                    ),
                    (
                        "Maximum modeled loss",
                        format_amount(
                            _first(plan, signal, "maximum_modeled_loss", "max_loss")
                        ),
                    ),
                )
            ),
        ),
        render_section("Next action", next_action),
    ]
    if reasons:
        sections.append(render_section("Blocked or rejected", render_bullets(reasons)))
    events = _sequence(trade.get("events"))
    fills = _sequence(trade.get("fills"))
    sections.append(
        render_section(
            "Lifecycle events",
            render_bullets(_event_lines(events) or (UNAVAILABLE,)),
        )
    )
    sections.append(
        render_section(
            "Fills and exits",
            render_bullets(_event_lines(fills) or (UNAVAILABLE,)),
        )
    )
    return "\n\n".join(sections)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _sequence(value: object) -> tuple[object, ...]:
    if isinstance(value, Sequence) and not isinstance(value, str | bytes):
        return tuple(value)
    return ()


def _yes_no(value: object) -> str:
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return UNAVAILABLE


def _r_multiple(value: object) -> str:
    rendered = format_ratio(value)
    return rendered if rendered == UNAVAILABLE else f"{rendered}R"


def _first(*sources_and_keys: object) -> object:
    sources: list[Mapping[str, object]] = []
    keys: list[str] = []
    reading_keys = False

    for value in sources_and_keys:
        if not reading_keys and isinstance(value, Mapping):
            sources.append(value)
            continue
        reading_keys = True
        keys.append(str(value))

    for key in keys:
        for source in sources:
            if source.get(key) is not None:
                return source[key]
    return None


def _leverage(plan: Mapping[str, object]) -> str:
    value = plan.get("leverage") or plan.get("selected_leverage")
    if isinstance(value, int | float) and not isinstance(value, bool):
        return f"{value:g}x"
    return UNAVAILABLE


def _integer(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _failure_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        if item:
            lines.append(f"{item.get('symbol', UNAVAILABLE)}: {item.get('reason', UNAVAILABLE)}")
        else:
            lines.append(str(value))
    return tuple(lines)


def _market_status_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        lines.append(
            f"{humanize_code(item.get('market_type'))}: "
            f"ready={_yes_no(item.get('operationally_ready'))}, "
            f"open={item.get('open_trade_count', 0)}, "
            f"closed={item.get('closed_trade_count', 0)}, "
            f"pipeline={humanize_code(item.get('latest_pipeline_outcome'))}"
        )
    return tuple(lines)


def _market_diagnostic_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        lines.append(
            f"{humanize_code(item.get('market_type'))}: "
            f"cycle_fresh={_yes_no(item.get('scheduler_fresh'))}, "
            f"intake_fresh={_yes_no(item.get('intake_fresh'))}, "
            f"pipeline_fresh={_yes_no(item.get('pipeline_fresh'))}, "
            f"failures={item.get('consecutive_pipeline_failures', 0)}, "
            f"provider_failures={item.get('latest_provider_failure_count', 0)}"
        )
    return tuple(lines)


def _guidance_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        lines.append(
            f"{item.get('symbol', UNAVAILABLE)} — "
            f"{humanize_code(item.get('paper_state'))}: "
            f"{item.get('instruction') or humanize_code(item.get('current_action'))}"
        )
    return tuple(lines)


def _trade_detail_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        lines.append(
            f"{item.get('symbol', UNAVAILABLE)} "
            f"| state={humanize_code(item.get('paper_state'))} "
            f"| action={humanize_code(item.get('current_action'))} "
            f"| id={item.get('trade_id', UNAVAILABLE)}"
        )
    return tuple(lines)


def _event_lines(values: Sequence[object]) -> tuple[str, ...]:
    lines: list[str] = []
    for value in values:
        item = _mapping(value)
        if item:
            label = item.get("event_type") or item.get("type") or item.get("state") or "event"
            detail = (
                item.get("reason")
                or item.get("price")
                or item.get("timestamp")
                or UNAVAILABLE
            )
            lines.append(f"{humanize_code(label)}: {detail}")
        else:
            lines.append(str(value))
    return tuple(lines)


def _cycle_next_action(
    cycle: Mapping[str, object], failures: Sequence[object]
) -> str:
    if failures:
        return "Review provider failures, then rerun the cycle after market data is healthy."
    if _integer(cycle.get("advanced_trade_count")) > 0:
        return (
            "Review advanced trades and any new fills, partial exits, "
            "invalidations, or completions."
        )
    return "No lifecycle change occurred. Continue scheduled collection."


def _pipeline_next_action(
    intake: Mapping[str, object],
    cycle: Mapping[str, object],
    failures: Sequence[object],
) -> str:
    if failures:
        return "Resolve provider failures before relying on this pipeline run."
    if _integer(intake.get("accepted")) > 0 or _integer(
        cycle.get("advanced_trade_count")
    ) > 0:
        return "Review newly accepted plans and lifecycle changes."
    return "Pipeline is healthy; continue accumulating paper-validation evidence."


def _status_next_action(
    payload: Mapping[str, object], markets: Sequence[object]
) -> str:
    if payload.get("operations_ready") is True:
        return "Operations are healthy. Continue scheduled paper collection and daily review."
    for value in markets:
        item = _mapping(value)
        if item.get("pipeline_lock_stale") is True or item.get("lock_stale") is True:
            return "Clear or investigate stale scheduler locks before the next run."
        if _integer(item.get("consecutive_pipeline_failures")) > 0:
            return (
                "Investigate the latest pipeline failure and restore successful "
                "scheduled runs."
            )
    return "Inspect freshness, malformed logs, provider failures, and missing reports."


def _trade_next_action(state: object, reasons: Sequence[object]) -> str:
    if reasons:
        return "Do not open the trade. Review the rejection reasons."
    normalized = str(getattr(state, "value", state) or "").upper()
    if "PARTIAL" in normalized:
        return "Protect the remaining position and follow the configured runner plan."
    if any(
        token in normalized
        for token in ("TARGET", "STOP", "COMPLETED", "CLOSED", "INVALID")
    ):
        return "No further execution action is required; retain the evidence for review."
    if "ENTER" in normalized:
        return "Monitor stop, targets, and lifecycle rules."
    return "Monitor the entry conditions and do not chase beyond the approved plan."


def _debug_fields(payload: Mapping[str, object]) -> str:
    return render_fields(
        (
            ("Top-level keys", ", ".join(sorted(str(key) for key in payload)) or UNAVAILABLE),
            ("Payload field count", len(payload)),
        )
    )


__all__ = [
    "render_paper_cycle",
    "render_paper_pipeline",
    "render_paper_report",
    "render_paper_status",
    "render_paper_trade",
]
