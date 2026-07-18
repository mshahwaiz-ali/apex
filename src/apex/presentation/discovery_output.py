"""Canonical text presentation for Stage 3 discovery output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    normalize_cli_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)
from apex.presentation.scan_groups import (
    flatten_existing_scan_groups,
    group_scan_results,
)


def render_discovery_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one canonical discovery result."""

    normalize_cli_output_mode(mode)
    symbol = str(payload.get("symbol") or "Unknown symbol")
    selected_setup = _mapping(payload.get("setup"))
    developing_setup = _mapping(payload.get("developing_setup"))
    focused = _mapping(payload.get("focused_analysis"))
    developing_only = not selected_setup and bool(developing_setup)
    setup = selected_setup or developing_setup
    if not setup:
        reasons = _strings(payload.get("reasons"))
        sections = [render_title(f"{symbol} — No Trade")]
        sections.extend(_focused_market_sections(focused))
        sections.append(
            render_section(
                "Current Decision",
                render_fields(
                    (
                        ("Trade now", "No"),
                        (
                            "Reason",
                            reasons[0] if reasons else "No defensible setup was selected",
                        ),
                        ("Candidates evaluated", payload.get("candidate_count")),
                    )
                ),
            )
        )
        sections.extend(_focused_direction_sections(focused))
        watch = _strings(focused.get("watch_plan"))
        if watch:
            sections.append(render_section("Watch Next", render_bullets(watch)))
        return "\n\n".join(sections)

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    policies = _mappings(setup.get("management_policies"))
    direction = humanize_code(setup.get("direction"))
    headline = str(setup.get("trader_headline") or f"{direction} setup")
    title = "Valid Setup, Entry Pending" if developing_only else headline
    sections = [render_title(f"{symbol} — {title}")]
    sections.extend(_focused_market_sections(focused))
    focused_assessment = _mapping(focused.get("directional_assessment"))
    if focused_assessment:
        sections.append(
            render_section(
                "Directional Assessment",
                render_fields(
                    (
                        ("Preferred side", humanize_code(focused_assessment.get("preferred_side"))),
                        ("Long thesis", humanize_code(focused_assessment.get("long_state"))),
                        ("Short thesis", humanize_code(focused_assessment.get("short_state"))),
                        ("Analytical confidence", focused_assessment.get("confidence_label")),
                        ("Reason", focused_assessment.get("reason")),
                    )
                ),
            )
        )
    sections.append(
        render_section(
            "Best Valid Pending Setup" if developing_only else "Selected Setup",
            render_fields(
                (
                    ("Group", humanize_code(payload.get("result_group"))),
                    ("Status", humanize_code(setup.get("entry_status"))),
                    ("Direction", direction),
                    ("Strategy", humanize_code(setup.get("strategy"))),
                    ("Rule-based quality", _quality_score(setup.get("confidence_score"))),
                    ("Execution allowed now", _yes_no(setup.get("execution_allowed_now"))),
                    ("Setup validity", setup.get("setup_validity")),
                )
            ),
        )
    )
    quality = _mapping(setup.get("quality_dimensions"))
    if quality:
        sections.append(
            render_section(
                "Trade Quality",
                render_fields(
                    (
                        ("Setup quality", format_score(quality.get("setup_quality"))),
                        ("Execution quality", format_score(quality.get("execution_quality"))),
                        ("Target quality", format_score(quality.get("target_quality"))),
                        ("Risk quality", format_score(quality.get("risk_quality"))),
                        (
                            "Overall trade quality",
                            format_score(quality.get("overall_trade_quality")),
                        ),
                    )
                ),
            )
        )

    entry_label, entry_value = _entry_display(entry.get("lower"), entry.get("upper"))
    trade_fields: list[tuple[str, object]] = [
        ("Current price", format_price(entry.get("current_price"))),
        (entry_label, entry_value),
        ("Preferred entry", format_price(entry.get("preferred"))),
        (_chase_label(setup), format_price(entry.get("maximum_chase_price"))),
        ("Structural stop", format_price(stop.get("price"))),
        ("Stop distance", f"{stop.get('distance_pct', 0):.2f}%"),
        ("Stop type", humanize_code(stop.get("stop_type"))),
        ("Single buffer", stop.get("single_buffer_rationale")),
        ("Stop quality", humanize_code(stop.get("quality_band"))),
    ]
    for index, target in enumerate(targets[:3], start=1):
        trade_fields.append(
            (
                f"TP{index}",
                f"{format_price(target.get('price'))} | "
                f"{format_ratio(target.get('risk_reward'))} | "
                f"close {target.get('partial_close_pct', 0):g}% | "
                f"{humanize_code(target.get('target_type'))} | "
                f"{target.get('purpose')}",
            )
        )
    sections.append(render_section("Trade Plan", render_fields(trade_fields)))

    alternatives = _mappings(setup.get("alternative_entry_opportunities"))
    if alternatives:
        alternative_lines = [
            (
                f"{_price_range(item.get('lower'), item.get('upper'))} | "
                f"preferred {format_price(item.get('preferred'))} | "
                f"max chase {format_price(item.get('maximum_chase_price'))}"
            )
            for item in alternatives[:4]
        ]
        sections.append(
            render_section("Alternative Entry Opportunities", render_bullets(alternative_lines))
        )

    expiry_reason = setup.get("setup_expiry_reason")
    if expiry_reason:
        sections.append(
            render_section(
                "Setup Validity",
                render_fields(
                    (
                        ("Duration", setup.get("setup_validity")),
                        ("Reason", expiry_reason),
                    )
                ),
            )
        )

    reasons = _strings(payload.get("reasons"))
    if reasons:
        reason_title = "Why Not Executable Now" if developing_only else "Why This Direction"
        sections.append(render_section(reason_title, render_bullets(reasons[:4])))

    if developing_only:
        activation_lines = _pending_activation_lines(setup)
        if activation_lines:
            sections.append(render_section("Activation Required", render_bullets(activation_lines)))

    entry_semantics = _mapping(payload.get("methodology_selected_entry_semantics"))
    if entry_semantics and not developing_only:
        sections.append(
            render_section(
                "Why This Entry",
                render_fields(
                    (
                        ("Selected kind", humanize_code(entry_semantics.get("selected_kind"))),
                        ("Executable now", _yes_no(entry_semantics.get("currently_executable"))),
                        ("Future trigger", _yes_no(entry_semantics.get("future_trigger_required"))),
                        ("Reason", entry_semantics.get("selection_reason")),
                    )
                ),
            )
        )

    invalidation = _mapping(payload.get("methodology_invalidation_semantics"))
    failure_event = invalidation.get("failure_event")
    if failure_event is not None and not developing_only:
        sections.append(
            render_section(
                "What Invalidates It",
                render_fields(
                    (
                        ("Failure event", failure_event),
                        ("Rule", humanize_code(invalidation.get("rule"))),
                        ("Structure", invalidation.get("structure")),
                    )
                ),
            )
        )

    target_semantics = _mapping(payload.get("methodology_target_feasibility_semantics"))
    if target_semantics and not developing_only:
        sections.append(
            render_section(
                "Why These Targets",
                render_fields(
                    (
                        ("Interpretation", target_semantics.get("interpretation")),
                        (
                            "Gross geometry",
                            _yes_no(target_semantics.get("gross_geometry_available")),
                        ),
                        ("Costs included", _yes_no(target_semantics.get("costs_available"))),
                    )
                ),
            )
        )

    candles = _mappings(payload.get("methodology_candlestick_evidence"))
    if candles:
        lines = [
            (
                f"{humanize_code(item.get('pattern_id'))}: "
                f"{humanize_code(item.get('pattern_direction'))} | "
                f"{humanize_code(item.get('completion_state'))} | "
                f"{item.get('context_note')}"
            )
            for item in candles[:3]
        ]
        sections.append(render_section("Candlestick Evidence", render_bullets(lines)))

    if policies:
        policy_lines = [
            f"{humanize_code(item.get('kind'))}: {item.get('action')} when {item.get('trigger')}"
            for item in policies
        ]
        sections.append(render_section("Trade Management", render_bullets(policy_lines)))

    warnings = _strings(setup.get("warnings"))
    if (
        not developing_only
        and target_semantics
        and target_semantics.get("costs_available") is not True
    ):
        warnings = (
            *warnings,
            "displayed reward geometry is gross; fees and slippage are not included",
        )
    if warnings:
        sections.append(render_section("Warnings", render_bullets(dict.fromkeys(warnings))))
    if focused:
        selected_direction = str(setup.get("direction") or "")
        opposite_key = "short_thesis" if selected_direction == "long" else "long_thesis"
        opposite = _mapping(focused.get(opposite_key))
        if opposite:
            sections.append(
                render_section(
                    f"{humanize_code(opposite.get('direction'))}-Side Assessment",
                    render_fields(
                        (
                            ("Status", humanize_code(opposite.get("state"))),
                            ("Strategy", humanize_code(opposite.get("primary_strategy"))),
                            ("Rule-based quality", _quality_score(opposite.get("score"))),
                            ("Outcome", humanize_code(opposite.get("candidate_outcome"))),
                            ("Reason", opposite.get("summary")),
                        )
                    ),
                )
            )
        watch = _strings(focused.get("watch_plan"))
        if watch:
            sections.append(render_section("Watch Next", render_bullets(watch)))
    return "\n\n".join(sections)


def render_discovery_scan(payload: Mapping[str, object]) -> str:
    """Render ranked canonical scan output grouped by actionability."""

    grouped = group_scan_results(flatten_existing_scan_groups(payload))
    sections = [render_title("Apex Futures Scan")]
    sections.append(
        render_section(
            "Scan Summary",
            render_fields(
                (
                    ("Markets analyzed", payload.get("total_analysis_count")),
                    ("Displayed candidates", payload.get("displayed_analysis_count")),
                    ("Selected setups", payload.get("selected_setup_count")),
                    ("Ready now", len(grouped.ready)),
                    ("Aggressive now", len(grouped.aggressive)),
                    ("Conditional entry", len(grouped.conditional)),
                    ("Developing/watch", len(grouped.developing)),
                    ("Late or invalidated", len(grouped.unavailable)),
                    ("No setup found", len(grouped.no_setup)),
                    ("Long candidates", payload.get("long_candidate_count")),
                    ("Short candidates", payload.get("short_candidate_count")),
                    ("Status counts", payload.get("status_counts")),
                )
            ),
        )
    )
    screening = _mapping(payload.get("screening"))
    lane_lines = _screening_lane_lines(screening)
    if lane_lines:
        sections.append(render_section("Discovery Lanes", render_bullets(lane_lines)))
    sections.extend(
        section
        for section in (
            _render_group("Ready Now", grouped.ready),
            _render_group("Aggressive Entries", grouped.aggressive),
            _render_group("Pullback / Retest / Reclaim Pending", grouped.conditional),
            _render_group("Developing / Watch", grouped.developing),
            _render_group("Late or Invalidated", grouped.unavailable),
            _render_group("No Setup Found", grouped.no_setup),
        )
        if section
    )
    return "\n\n".join(sections)


def _render_group(title: str, results: Sequence[Mapping[str, object]]) -> str:
    if not results:
        return ""
    cards = [_render_scan_card(item) for item in results]
    separator = "\n\n" + "═" * 56 + "\n\n"
    return render_section(title, separator.join(cards))


def _render_scan_card(payload: Mapping[str, object]) -> str:
    symbol = str(payload.get("symbol") or "Unknown symbol")
    selected = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    setup = selected or developing
    if not setup:
        reasons = _strings(payload.get("reasons"))
        return "\n".join(
            (
                f"{symbol} — No Trade",
                f"  Reason     : {reasons[0] if reasons else 'No defensible setup was selected'}",
                f"  Candidates : {payload.get('candidate_count')}",
            )
        )

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    direction = humanize_code(setup.get("direction"))
    state = "Entry Pending" if developing and not selected else "Selected Setup"
    fields: list[tuple[str, object]] = [
        ("State", state),
        ("Status", humanize_code(setup.get("entry_status"))),
        ("Direction", direction),
        ("Strategy", humanize_code(setup.get("strategy"))),
        ("Rule-based quality", _quality_score(setup.get("confidence_score"))),
        ("Current price", format_price(entry.get("current_price"))),
        ("Preferred entry", format_price(entry.get("preferred"))),
        ("Stop", format_price(stop.get("price"))),
    ]
    if targets:
        fields.append(
            ("Targets", " / ".join(format_price(item.get("price")) for item in targets[:3]))
        )
    if developing and not selected:
        fields.extend(
            (
                ("Activation", _pending_activation_summary(setup)),
                ("Valid for", setup.get("setup_validity")),
                ("Inspect", f"apex analyze {symbol.replace('/', '')}"),
            )
        )
    return "\n".join((f"{symbol} — {state}", render_fields(fields)))


def _pending_activation_lines(setup: Mapping[str, object]) -> tuple[str, ...]:
    warnings = _strings(setup.get("warnings"))
    material = tuple(
        warning
        for warning in warnings
        if "confirmation" in warning.lower()
        or "provisional" in warning.lower()
        or "retest" in warning.lower()
        or "reclaim" in warning.lower()
        or "pullback" in warning.lower()
    )
    if material:
        return tuple(dict.fromkeys(material))[:4]
    status = humanize_code(setup.get("entry_status"))
    return (f"{status} must transition to an executable entry state",)


def _pending_activation_summary(setup: Mapping[str, object]) -> str:
    lines = _pending_activation_lines(setup)
    return lines[0] if lines else "execution confirmation remains incomplete"


def _focused_market_sections(focused: Mapping[str, object]) -> list[str]:
    outlook = _mapping(focused.get("market_outlook"))
    if not outlook:
        return []
    return [
        render_section(
            "Market Outlook",
            render_fields(
                (
                    ("Regime", humanize_code(outlook.get("regime"))),
                    ("Market condition", humanize_code(outlook.get("market_condition"))),
                    ("Primary structure", humanize_code(outlook.get("primary_structure"))),
                    ("Setup structure", humanize_code(outlook.get("setup_structure"))),
                    ("Entry timeframe", outlook.get("entry_timeframe")),
                    ("Volatility", humanize_code(outlook.get("volatility"))),
                    ("Participation", humanize_code(outlook.get("participation"))),
                    ("Current location", outlook.get("current_location")),
                )
            ),
        )
    ]


def _focused_direction_sections(focused: Mapping[str, object]) -> list[str]:
    if not focused:
        return []
    sections: list[str] = []
    assessment = _mapping(focused.get("directional_assessment"))
    if assessment:
        sections.append(
            render_section(
                "Directional Assessment",
                render_fields(
                    (
                        ("Preferred side", humanize_code(assessment.get("preferred_side"))),
                        ("Long thesis", humanize_code(assessment.get("long_state"))),
                        ("Short thesis", humanize_code(assessment.get("short_state"))),
                        ("Analytical confidence", assessment.get("confidence_label")),
                        ("Reason", assessment.get("reason")),
                    )
                ),
            )
        )
    for title, key in (("Long Assessment", "long_thesis"), ("Short Assessment", "short_thesis")):
        thesis = _mapping(focused.get(key))
        if not thesis:
            continue
        sections.append(
            render_section(
                title,
                render_fields(
                    (
                        ("Status", humanize_code(thesis.get("state"))),
                        ("Strategy", humanize_code(thesis.get("primary_strategy"))),
                        ("Rule-based quality", _quality_score(thesis.get("score"))),
                        ("Required threshold", _quality_score(thesis.get("approval_threshold"))),
                        ("Shortfall", _score_shortfall(thesis.get("score_shortfall"))),
                        ("Outcome", humanize_code(thesis.get("candidate_outcome"))),
                        ("Summary", thesis.get("summary")),
                    )
                ),
            )
        )
        blockers = _strings(thesis.get("blockers"))
        activation = _strings(thesis.get("activation_conditions"))
        invalidation = _strings(thesis.get("invalidation_conditions"))
        if blockers:
            sections.append(render_section(f"{title} Blockers", render_bullets(blockers[:5])))
        if activation:
            sections.append(render_section(f"{title} Activation", render_bullets(activation[:4])))
        if invalidation:
            sections.append(
                render_section(f"{title} Invalidation", render_bullets(invalidation[:3]))
            )
    return sections


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _screening_lane_lines(screening: Mapping[str, object]) -> tuple[str, ...]:
    candidates = _mappings(screening.get("candidates"))
    lines: list[str] = []
    for candidate in candidates[:5]:
        lanes = _mappings(candidate.get("discovery_lanes"))
        if not lanes:
            continue
        primary = lanes[0]
        lines.append(
            f"{candidate.get('symbol')}: {humanize_code(primary.get('lane'))} "
            f"({format_score(primary.get('score'))}) — {primary.get('reason')}"
        )
    return tuple(lines)


def _yes_no(value: object) -> str:
    if value is True:
        return "Yes"
    if value is False:
        return "No"
    return "Unavailable"


def _price_range(low: object, high: object) -> str:
    if low is None and high is None:
        return "Unavailable"
    if low is None:
        return format_price(high)
    if high is None:
        return format_price(low)
    return f"{format_price(low)} - {format_price(high)}"


def _entry_display(low: object, high: object) -> tuple[str, str]:
    if low is not None and high is not None and low == high:
        return "Entry price", format_price(low)
    return "Entry zone", _price_range(low, high)


def _quality_score(value: object) -> str:
    formatted = format_score(value)
    return formatted if formatted == "Unavailable" else f"{formatted}/100"


def _score_shortfall(value: object) -> str:
    formatted = format_score(value)
    return formatted if formatted == "Unavailable" else f"{formatted} points"


def _chase_label(setup: Mapping[str, object]) -> str:
    direction = str(setup.get("direction") or "").lower()
    if direction == "short":
        return "Do not sell below"
    if direction == "long":
        return "Do not buy above"
    return "Maximum chase"


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
