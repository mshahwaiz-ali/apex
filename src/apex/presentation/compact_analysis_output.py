"""Compact professional renderer for selected-symbol analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from apex.presentation import (
    format_price,
    format_score,
    humanize_code,
    render_fields,
    render_section,
    render_title,
)

_SUPPRESSED_PLAN_WARNING = (
    "confirmation-required setup has no post-confirmation execution room "
    "while preserving minimum net reward-to-risk"
)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _percentage(price: object, reference: object) -> str:
    price_number = _number(price)
    reference_number = _number(reference)
    if price_number is None or reference_number is None or reference_number == 0.0:
        return "Unavailable"
    move = (price_number - reference_number) / reference_number * 100.0
    return f"{move:+.2f}%"


def _timestamp(value: object) -> str:
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S UTC")
    if value is None:
        return "Unavailable"
    text = str(value).replace("T", " ").replace("+00:00", " UTC")
    return text[:-1] + " UTC" if text.endswith("Z") else text


def _entry_line(entry: Mapping[str, object]) -> tuple[str, object]:
    lower = _number(entry.get("lower"))
    upper = _number(entry.get("upper"))
    if (
        lower is not None
        and upper is not None
        and abs(lower - upper) <= max(abs(lower), 1.0) * 1e-12
    ):
        return ("Entry", format_price(lower))
    return (
        "Entry zone",
        f"{format_price(entry.get('lower'))} - {format_price(entry.get('upper'))}",
    )


def _conditional_plan(setup: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(setup.get("conditional_plan"))


def _warnings(setup: Mapping[str, object]) -> tuple[str, ...]:
    warnings = setup.get("warnings")
    if not isinstance(warnings, Sequence) or isinstance(warnings, str | bytes):
        return ()
    return tuple(str(item) for item in warnings)


def _activation_plan_suppressed(setup: Mapping[str, object]) -> bool:
    if _conditional_plan(setup):
        return False
    return any(_SUPPRESSED_PLAN_WARNING in warning.lower() for warning in _warnings(setup))


def _trigger_payload(setup: Mapping[str, object]) -> Mapping[str, object]:
    return _mapping(_conditional_plan(setup).get("trigger"))


def _trigger_kind(setup: Mapping[str, object]) -> str:
    trigger = _trigger_payload(setup)
    value = trigger.get("type") or trigger.get("kind")
    return "" if value is None else str(value).lower()


def _status(setup: Mapping[str, object]) -> str:
    if setup.get("execution_allowed_now") is True:
        return "Ready now"
    if _activation_plan_suppressed(setup):
        return "Setup valid - activation blocked"
    trigger_kind = _trigger_kind(setup)
    if trigger_kind == "retest_hold":
        return "Future retest - hold required"
    if trigger_kind == "reclaim_close":
        return "Future reclaim - close required"
    state = setup.get("entry_status") or setup.get("actionability_state")
    if state is not None:
        human = humanize_code(state)
        if human.lower() not in {"unavailable", "none"}:
            return human
    if _conditional_plan(setup):
        return "Awaiting confirmation"
    return "Valid setup - monitor"


def _strategy(setup: Mapping[str, object], opportunity: Mapping[str, object]) -> str:
    return humanize_code(setup.get("strategy") or opportunity.get("strategy"))


def _direction(setup: Mapping[str, object], opportunity: Mapping[str, object]) -> str:
    return humanize_code(opportunity.get("direction") or setup.get("direction")).upper()


def _relationship(setup: Mapping[str, object]) -> str:
    layered = _mapping(setup.get("layered_state"))
    relationship = (
        setup.get("trend_relationship")
        or setup.get("parent_thesis_state")
        or layered.get("timeframe_relationship")
    )
    return humanize_code(relationship) if relationship is not None else "Unavailable"


def _timeframe_context(setup: Mapping[str, object]) -> str:
    layered = _mapping(setup.get("layered_state"))
    values = tuple(
        humanize_code(value)
        for value in (
            layered.get("structural_bias"),
            layered.get("timeframe_relationship"),
            layered.get("relationship_severity"),
            layered.get("holding_horizon"),
        )
        if value not in {None, "", "unavailable"}
    )
    return " • ".join(values) if values else "Not published"


def _trigger(setup: Mapping[str, object]) -> str:
    trigger = _trigger_payload(setup)
    if not trigger:
        if setup.get("execution_allowed_now") is True:
            return "No additional trigger required"
        if _activation_plan_suppressed(setup):
            return "Suppressed - no valid post-confirmation entry remains"
        return "Monitor stated entry conditions"
    kind = humanize_code(trigger.get("type") or trigger.get("kind"))
    level = format_price(trigger.get("level"))
    timeframe = trigger.get("confirmation_timeframe")
    suffix = "" if timeframe in {None, ""} else f" on {timeframe}"
    return f"{kind} at {level}{suffix}"


def _pre_entry_invalidation(setup: Mapping[str, object]) -> str:
    plan = _conditional_plan(setup)
    invalidation = _mapping(plan.get("pre_entry_invalidation"))
    if invalidation:
        return format_price(invalidation.get("price"))
    if _activation_plan_suppressed(setup):
        return "Not applicable - activation plan suppressed"
    return "Unavailable"


def _quality(setup: Mapping[str, object], opportunity: Mapping[str, object]) -> str:
    quality = _mapping(setup.get("quality_dimensions"))
    return format_score(
        opportunity.get("final_score")
        or setup.get("confidence_score")
        or quality.get("overall_trade_quality")
    )


def _price_move(price: object, reference: object) -> str:
    return f"{format_price(price)}  {_percentage(price, reference)}"


def _target_context(target: Mapping[str, object]) -> str:
    rationale = target.get("rationale")
    basis = ""
    if isinstance(rationale, Sequence) and not isinstance(rationale, str | bytes):
        basis = next((str(item).strip() for item in rationale if str(item).strip()), "")
    timeframe = target.get("target_timeframe")
    timeframe_text = "" if timeframe in {None, ""} else str(timeframe).strip()
    if basis:
        return basis
    if timeframe_text:
        return f"{timeframe_text} target structure"
    return ""


def _target_line(target: Mapping[str, object], reference: object) -> str:
    value = _price_move(target.get("price"), reference)
    context = _target_context(target)
    return value if not context else f"{value}  • {context}"


def _execution_label(setup: Mapping[str, object]) -> str:
    if setup.get("execution_allowed_now") is True:
        return "Executable now"
    if _activation_plan_suppressed(setup):
        return "Monitor only - activation blocked"
    authority = humanize_code(setup.get("execution_authority"))
    return "Do not enter now" if authority == "Unavailable" else authority


def _plan_title(setup: Mapping[str, object], index: int) -> str:
    if setup.get("execution_allowed_now") is True:
        return f"TRADE {index}"
    if _activation_plan_suppressed(setup):
        return f"SETUP PLAN {index} • ACTIVATION BLOCKED"
    trigger_kind = _trigger_kind(setup)
    if trigger_kind == "retest_hold":
        return f"SETUP PLAN {index} • FUTURE RETEST"
    if trigger_kind == "reclaim_close":
        return f"SETUP PLAN {index} • FUTURE RECLAIM"
    return f"SETUP PLAN {index} • CONDITIONAL"


def _risk_reward(target: Mapping[str, object]) -> str:
    net = _number(target.get("net_risk_reward"))
    gross = _number(target.get("risk_reward"))
    if net is not None:
        return f"{net:.2f}R net"
    if gross is not None:
        return f"{gross:.2f}R gross"
    return "Unavailable"


def _expiry(plan: Mapping[str, object]) -> str:
    expiry = _mapping(plan.get("expiry"))
    bars = expiry.get("bars")
    seconds = expiry.get("seconds")
    reason = expiry.get("reason")
    if bars is not None:
        return f"{bars} bars" + (f" - {reason}" if reason else "")
    if seconds is not None:
        return f"{seconds} seconds" + (f" - {reason}" if reason else "")
    return "Not configured"


def _activation_suppression_reason(targets: tuple[Mapping[str, object], ...]) -> str:
    if targets:
        reward = _risk_reward(targets[0])
        if reward != "Unavailable":
            return f"Only {reward} remains after confirmation and costs"
    return "Minimum post-confirmation net reward-to-risk cannot be preserved"


def _trade_card(
    opportunity: Mapping[str, object],
    *,
    index: int,
    symbol: str,
    generated_at: object,
    explain: bool,
) -> str:
    setup = _mapping(opportunity.get("setup")) or opportunity
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    plan = _conditional_plan(setup)
    trigger = _trigger_payload(setup)
    reference = entry.get("preferred") or entry.get("current_price")
    direction = _direction(setup, opportunity)
    strategy = _strategy(setup, opportunity)
    activation_suppressed = _activation_plan_suppressed(setup)

    entry_fields: list[tuple[str, object]] = [
        ("CMP", format_price(entry.get("current_price"))),
        _entry_line(entry),
        ("Ideal entry", format_price(entry.get("preferred"))),
    ]
    maximum_chase = entry.get("maximum_chase_price")
    if maximum_chase is not None:
        entry_fields.append(("Maximum chase", format_price(maximum_chase)))

    body: list[str] = [
        render_fields(
            (
                ("Status", _status(setup)),
                ("Execution", _execution_label(setup)),
                ("Confidence", f"{_quality(setup, opportunity)}/100"),
                ("Generated", _timestamp(generated_at)),
            )
        ),
        "",
        "  ENTRY",
        render_fields(tuple(entry_fields)),
        "",
        "  RISK",
        render_fields(
            (
                ("Post-entry stop", _price_move(stop.get("price"), reference)),
                ("Pre-entry invalidation", _pre_entry_invalidation(setup)),
            )
        ),
    ]

    if targets:
        body.extend(("", "  TARGETS"))
        body.append(
            render_fields(
                tuple(
                    (
                        f"TP{target_index}",
                        _target_line(target, reference),
                    )
                    for target_index, target in enumerate(targets[:3], start=1)
                )
            )
        )

    setup_fields: list[tuple[str, object]] = [
        ("Trend", _relationship(setup)),
        ("Trigger", _trigger(setup)),
    ]
    if activation_suppressed:
        setup_fields.extend(
            (
                ("Activation plan", "Suppressed"),
                ("Reason", _activation_suppression_reason(targets)),
                ("Next action", "Monitor only - do not enter at CMP"),
            )
        )
    else:
        setup_fields.append(
            (
                "Next action",
                plan.get("reason_not_executable_now")
                or "Follow the published activation condition",
            )
        )

    body.extend(("", "  SETUP", render_fields(tuple(setup_fields))))

    if explain:
        quality = _mapping(setup.get("quality_dimensions"))
        geometry = _mapping(plan.get("geometry"))
        warning_values = _warnings(setup)
        explanation_fields: list[tuple[str, object]] = [
            ("Setup quality", f"{format_score(quality.get('setup_quality'))}/100"),
            (
                "Execution quality",
                f"{format_score(quality.get('execution_quality'))}/100",
            ),
            ("Target quality", f"{format_score(quality.get('target_quality'))}/100"),
            ("Execution authority", humanize_code(setup.get("execution_authority"))),
            ("Entry mode", humanize_code(setup.get("entry_mode"))),
            ("Timeframe context", _timeframe_context(setup)),
            ("Gross / net R", _risk_reward(targets[0]) if targets else "Unavailable"),
        ]
        if activation_suppressed:
            explanation_fields.extend(
                (
                    ("Activation plan", "Suppressed"),
                    ("Suppression reason", _activation_suppression_reason(targets)),
                    ("Confirmation TF", "Not applicable - no authorised trigger"),
                    ("Order intent", "None - monitor only"),
                    ("Setup expiry", "Not applicable - no active plan"),
                )
            )
        else:
            explanation_fields.extend(
                (
                    ("Trigger condition", trigger.get("condition") or "Unavailable"),
                    (
                        "Confirmation TF",
                        trigger.get("confirmation_timeframe") or "Unavailable",
                    ),
                    ("Order intent", humanize_code(plan.get("recommended_order_intent"))),
                    ("Stop basis", humanize_code(geometry.get("stop_basis"))),
                    ("Target basis", humanize_code(geometry.get("targets_basis"))),
                    ("Setup expiry", _expiry(plan)),
                )
            )
        if len(targets) == 1:
            explanation_fields.append(
                ("Additional targets", "Not published - no verified structure")
            )
        body.extend(
            (
                "",
                "  WHY THIS TRADE",
                render_fields(tuple(explanation_fields)),
            )
        )
        if warning_values:
            body.extend(
                (
                    "",
                    "  WARNINGS",
                    "\n".join(f"    - {value}" for value in warning_values),
                )
            )

    title = f"{_plan_title(setup, index)} • {symbol} • {direction} • {strategy}"
    return render_section(title, "\n".join(body))


def _collect_opportunities(payload: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    portfolio = _mapping(payload.get("opportunity_portfolio"))
    groups = (
        _mappings(portfolio.get("current_opportunities")),
        _mappings(portfolio.get("nearby_opportunities")),
        _mappings(portfolio.get("follow_up_opportunities")),
        _mappings(portfolio.get("runner_opportunities")),
        _mappings(portfolio.get("opportunities")),
    )
    collected: list[Mapping[str, object]] = []
    seen: set[str] = set()
    for group in groups:
        for opportunity in group:
            setup = _mapping(opportunity.get("setup")) or opportunity
            identity = str(
                opportunity.get("candidate_id")
                or setup.get("candidate_id")
                or (
                    opportunity.get("direction"),
                    setup.get("strategy"),
                    _mapping(setup.get("entry")).get("preferred"),
                )
            )
            if identity in seen:
                continue
            seen.add(identity)
            collected.append(opportunity)

    if not collected:
        for key in ("setup", "developing_setup"):
            setup = _mapping(payload.get(key))
            if setup:
                collected.append(setup)
    return tuple(collected)


def render_compact_analysis(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render analysis as compact, sequential, trader-oriented blocks."""

    symbol = str(payload.get("symbol") or "Unknown market")
    generated_at = payload.get("generated_at")
    portfolio = _mapping(payload.get("opportunity_portfolio"))
    opportunities = _collect_opportunities(payload)

    sections = [render_title(f"Apex Analysis • {symbol}")]
    sections.append(
        render_section(
            "MARKET VIEW",
            render_fields(
                (
                    ("CMP", format_price(portfolio.get("cmp"))),
                    ("Generated", _timestamp(generated_at)),
                    ("Trade opportunities", len(opportunities)),
                    ("Decision", humanize_code(portfolio.get("decision"))),
                )
            ),
        )
    )

    if opportunities:
        sections.extend(
            _trade_card(
                opportunity,
                index=index,
                symbol=symbol,
                generated_at=generated_at,
                explain=explain,
            )
            for index, opportunity in enumerate(opportunities, start=1)
        )
    else:
        plan = _mapping(payload.get("setup_plan"))
        sections.append(
            render_section(
                "Decision",
                render_fields(
                    (
                        ("Status", "No valid setup yet"),
                        ("Current state", plan.get("current_state")),
                        ("Long trigger", plan.get("long_trigger")),
                        ("Short trigger", plan.get("short_trigger")),
                        (
                            "Next action",
                            "Re-run after a material structure or entry-condition change",
                        ),
                    )
                ),
            )
        )
    return "\n\n".join(sections)


__all__ = ["render_compact_analysis"]
