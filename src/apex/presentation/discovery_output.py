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
    setup = _mapping(payload.get("setup"))
    if not setup:
        reasons = _strings(payload.get("reasons"))
        sections = [render_title(f"{symbol} — No Trade")]
        sections.append(
            render_section(
                "Assessment",
                render_fields(
                    (
                        ("Status", "No trade"),
                        ("Reason", reasons[0] if reasons else "No defensible setup was selected"),
                        ("Candidates evaluated", payload.get("candidate_count")),
                    )
                ),
            )
        )
        return "\n\n".join(sections)

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    policies = _mappings(setup.get("management_policies"))
    direction = humanize_code(setup.get("direction"))
    headline = str(setup.get("trader_headline") or f"{direction} setup")
    sections = [render_title(f"{symbol} — {headline}")]
    sections.append(
        render_section(
            "Selected Setup",
            render_fields(
                (
                    ("Group", humanize_code(payload.get("result_group"))),
                    ("Status", humanize_code(setup.get("entry_status"))),
                    ("Direction", direction),
                    ("Strategy", humanize_code(setup.get("strategy"))),
                    ("Confidence", format_score(setup.get("confidence_score"))),
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
        ("Maximum chase", format_price(entry.get("maximum_chase_price"))),
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
        sections.append(render_section("Why This Direction", render_bullets(reasons[:4])))

    entry_semantics = _mapping(payload.get("methodology_selected_entry_semantics"))
    if entry_semantics:
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
    if failure_event is not None:
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
    if target_semantics:
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
    if target_semantics and target_semantics.get("costs_available") is not True:
        warnings = (
            *warnings,
            "displayed reward geometry is gross; fees and slippage are not included",
        )
    if warnings:
        sections.append(render_section("Warnings", render_bullets(dict.fromkeys(warnings))))
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
    cards = [render_discovery_analysis(item) for item in results]
    separator = "\n\n" + "═" * 56 + "\n\n"
    return render_section(title, separator.join(cards))


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


__all__ = ["render_discovery_analysis", "render_discovery_scan"]
