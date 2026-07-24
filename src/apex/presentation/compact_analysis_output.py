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


def _status(setup: Mapping[str, object]) -> str:
    if setup.get("execution_allowed_now") is True:
        return "Ready now"
    state = setup.get("entry_status") or setup.get("actionability_state")
    if state is not None:
        human = humanize_code(state)
        if human.lower() not in {"unavailable", "none"}:
            return human
    if _mapping(setup.get("conditional_plan")):
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


def _trigger(setup: Mapping[str, object]) -> str:
    plan = _mapping(setup.get("conditional_plan"))
    trigger = _mapping(plan.get("trigger"))
    if not trigger:
        if setup.get("execution_allowed_now") is True:
            return "No additional trigger required"
        return "Monitor stated entry conditions"
    kind = humanize_code(trigger.get("type") or trigger.get("kind"))
    level = format_price(trigger.get("level"))
    return f"{kind} at {level}"


def _invalidation(setup: Mapping[str, object]) -> str:
    plan = _mapping(setup.get("conditional_plan"))
    invalidation = _mapping(plan.get("pre_entry_invalidation"))
    if invalidation:
        return format_price(invalidation.get("price"))
    stop = _mapping(setup.get("stop_loss"))
    return format_price(stop.get("price"))


def _quality(setup: Mapping[str, object], opportunity: Mapping[str, object]) -> str:
    quality = _mapping(setup.get("quality_dimensions"))
    return format_score(
        opportunity.get("final_score")
        or setup.get("confidence_score")
        or quality.get("overall_trade_quality")
    )


def _price_move(price: object, reference: object) -> str:
    return f"{format_price(price)}  {_percentage(price, reference)}"


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
    reference = entry.get("preferred") or entry.get("current_price")
    direction = _direction(setup, opportunity)
    strategy = _strategy(setup, opportunity)

    body: list[str] = [
        render_fields(
            (
                ("Status", _status(setup)),
                ("Confidence", f"{_quality(setup, opportunity)}/100"),
                ("Generated", _timestamp(generated_at)),
            )
        ),
        "",
        "  ENTRY",
        render_fields(
            (
                ("CMP", format_price(entry.get("current_price"))),
                _entry_line(entry),
                ("Ideal entry", format_price(entry.get("preferred"))),
            )
        ),
        "",
        "  RISK",
        render_fields((("Stop loss", _price_move(stop.get("price"), reference)),)),
    ]

    if targets:
        body.extend(("", "  TARGETS"))
        body.append(
            render_fields(
                tuple(
                    (
                        f"TP{target_index}",
                        _price_move(target.get("price"), reference),
                    )
                    for target_index, target in enumerate(targets[:3], start=1)
                )
            )
        )

    body.extend(
        (
            "",
            "  SETUP",
            render_fields(
                (
                    ("Trend", _relationship(setup)),
                    ("Trigger", _trigger(setup)),
                    ("Invalidation", _invalidation(setup)),
                )
            ),
        )
    )

    if explain:
        quality = _mapping(setup.get("quality_dimensions"))
        warnings = setup.get("warnings")
        warning_values = (
            tuple(str(item) for item in warnings)
            if isinstance(warnings, Sequence) and not isinstance(warnings, str | bytes)
            else ()
        )
        body.extend(
            (
                "",
                "  WHY THIS TRADE",
                render_fields(
                    (
                        ("Setup quality", f"{format_score(quality.get('setup_quality'))}/100"),
                        (
                            "Execution quality",
                            f"{format_score(quality.get('execution_quality'))}/100",
                        ),
                        ("Target quality", f"{format_score(quality.get('target_quality'))}/100"),
                        (
                            "Execution authority",
                            humanize_code(setup.get("execution_authority")),
                        ),
                        ("Entry mode", humanize_code(setup.get("entry_mode"))),
                    )
                ),
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

    title = f"TRADE {index} • {symbol} • {direction} • {strategy}"
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
