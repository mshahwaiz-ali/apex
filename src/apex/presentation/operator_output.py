"""Clean, trader-facing scan and analysis reports."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence

from apex.presentation import (
    UNAVAILABLE,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)
from apex.presentation.cli_information_architecture import (
    data_quality_warning,
    diagnostic_summary_lines,
    entry_distance_label,
    evidence_contradiction_lines,
    multi_timeframe_lines,
    opportunity_map_lines,
    partition_scan_results,
    rationale_lines,
    rejected_candidate_lines,
)
from apex.presentation.scan_groups import flatten_existing_scan_groups


def render_analysis(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render one decision as a short action-first report."""

    symbol = str(payload.get("symbol") or "Unknown market")
    selected = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    setup = selected or developing
    focused = _mapping(payload.get("focused_analysis"))
    sections = [render_title(f"Apex Analysis • {symbol}")]

    if not setup:
        sections.extend(_no_trade_sections(payload, focused, explain=explain))
    else:
        sections.extend(
            _setup_sections(
                payload,
                setup,
                focused,
                pending=bool(developing and not selected),
                explain=explain,
            )
        )
    return "\n\n".join(section for section in sections if section)


def render_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render the ranked scan as a compact action board."""

    grouped = partition_scan_results(flatten_existing_scan_groups(payload))
    visible = grouped.visible_count
    sections = [render_title("Apex Market Scan • Opportunity Board")]
    sections.append(
        render_section(
            "At a glance",
            render_fields(
                (
                    ("Markets checked", payload.get("total_analysis_count")),
                    ("Actionable at CMP", len(grouped.actionable_cmp)),
                    ("Nearby limit entries", len(grouped.nearby_limit)),
                    ("Micro-confirmation entries", len(grouped.micro_confirmation)),
                    ("Follow-up / reversal", len(grouped.follow_up_reversal)),
                    ("Weak / invalid", len(grouped.weak_invalid)),
                    ("Action", "Review the highest section first" if visible else "Stay patient"),
                )
            ),
        )
    )
    for title, hint, items in (
        (
            "Actionable at CMP",
            "Current market price is inside an executable opportunity.",
            grouped.actionable_cmp,
        ),
        (
            "Nearby limit entries",
            "A valid entry exists near CMP but price has not reached it.",
            grouped.nearby_limit,
        ),
        (
            "Micro-confirmation entries",
            "Wait only for the stated reclaim, close, or micro trigger.",
            grouped.micro_confirmation,
        ),
        (
            "Follow-up / reversal setups",
            "Sequential, reversal, or developing opportunities; not executable yet.",
            grouped.follow_up_reversal,
        ),
    ):
        if items:
            sections.append(_scan_group(title, hint, items))
    if grouped.weak_invalid:
        sections.append(
            render_section(
                f"Weak or invalid setup summary ({len(grouped.weak_invalid)})",
                "These markets were retained in the count but are not executable.",
            )
        )
    screening = _mapping(payload.get("screening"))
    lanes = _screening_lanes(screening)
    if lanes:
        sections.append(
            render_section(
                "Why these markets were shortlisted • Discovery Lanes", render_bullets(lanes)
            )
        )
    if explain:
        sections.append(
            render_section(
                "Full scan counts",
                render_fields(
                    (
                        ("Displayed", payload.get("displayed_analysis_count")),
                        ("Selected setups", payload.get("selected_setup_count")),
                        ("Long candidates", payload.get("long_candidate_count")),
                        ("Short candidates", payload.get("short_candidate_count")),
                        ("Weak / invalid", len(grouped.weak_invalid)),
                        (
                            "Not silently displayed",
                            max(
                                0,
                                _count(payload.get("total_analysis_count"))
                                - _count(payload.get("displayed_analysis_count")),
                            ),
                        ),
                    )
                ),
            )
        )
    return "\n\n".join(sections)


def _no_trade_sections(
    payload: Mapping[str, object],
    focused: Mapping[str, object],
    *,
    explain: bool,
) -> list[str]:
    assessment = _mapping(focused.get("directional_assessment"))
    reasons = _clean_many(payload.get("reasons"))
    reason = reasons[0] if reasons else "No setup currently offers a clear entry and defined risk."
    sections = [
        render_section(
            "Decision",
            "\n".join(
                (
                    "▶  WAIT — NO TRADE RIGHT NOW",
                    render_fields(
                        (
                            (
                                "Directional Assessment",
                                humanize_code(assessment.get("preferred_side")),
                            ),
                            ("Why", reason),
                            ("Setups checked", payload.get("candidate_count")),
                        )
                    ),
                )
            ),
        )
    ]
    context = _market_context(focused)
    if context:
        sections.append(context)
    signal = _signal_snapshot(payload)
    if signal:
        sections.append(signal)
    watch = _watch_items(focused)
    if watch:
        sections.append(render_section("Watch Next", render_bullets(watch[:5])))
    sections.extend(_side_explanation(focused, include_blockers=explain))
    return sections


def _setup_sections(
    payload: Mapping[str, object],
    setup: Mapping[str, object],
    focused: Mapping[str, object],
    *,
    pending: bool,
    explain: bool,
) -> list[str]:
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    direction = humanize_code(setup.get("direction"))
    actionability = str(setup.get("actionability_state") or "").lower()
    terminal_actionability = actionability in {
        "invalidated",
        "missed_or_chasing",
    }
    executable_actionability = actionability in {
        "execute_now",
        "aggressive_now",
    }
    micro_confirmation = actionability == "execute_on_micro_confirmation"
    executable = executable_actionability and not pending and not terminal_actionability
    if executable:
        action = f"ENTER {direction.upper()}"
    elif micro_confirmation and not pending:
        action = "WAIT FOR MICRO CONFIRMATION"
    elif terminal_actionability:
        action = "SKIP — INVALID OR CHASED"
    else:
        action = "WAIT FOR ACTIVATION"
    sections = [
        render_section(
            "Decision",
            "\n".join(
                (
                    f"▶  {action}",
                    render_fields(
                        (
                            (
                                "Setup",
                                "Valid Setup, Entry Pending"
                                if pending
                                else setup.get("trader_headline") or "Valid setup",
                            ),
                            ("Direction", direction),
                            ("Strategy", humanize_code(setup.get("strategy"))),
                            (
                                "Actionability",
                                humanize_code(
                                    setup.get("actionability_state") or setup.get("entry_status")
                                ),
                            ),
                            (
                                "Activation basis",
                                humanize_code(setup.get("actionability_basis")),
                            ),
                            ("Setup quality", _quality(setup.get("confidence_score"))),
                            (
                                "Execution allowed now",
                                _yes_no(setup.get("execution_allowed_now")),
                            ),
                        )
                    ),
                )
            ),
        )
    ]
    entry_label = (
        "Entry price"
        if entry.get("lower") is not None and entry.get("lower") == entry.get("upper")
        else "Entry zone"
    )
    plan: list[tuple[str, object]] = [
        ("Current price", format_price(entry.get("current_price"))),
        (entry_label, _price_range(entry.get("lower"), entry.get("upper"))),
        ("Preferred entry", format_price(entry.get("preferred"))),
        ("Invalidation / stop", format_price(stop.get("price"))),
    ]
    if setup.get("direction") == "short":
        plan.append(("Do not chase below", format_price(entry.get("maximum_chase_price"))))
    else:
        plan.append(("Do not chase above", format_price(entry.get("maximum_chase_price"))))
    for index, target in enumerate(targets[:3], start=1):
        purpose = str(target.get("purpose")) if target.get("purpose") else ""
        plan.append(
            (
                f"Target {index}",
                f"{format_price(target.get('price'))}  •  "
                f"{format_ratio(target.get('risk_reward'))}R",
            )
        )
        if purpose:
            plan.append((f"Target {index} purpose", purpose))
    if stop.get("single_buffer_rationale"):
        plan.append(("Stop rationale", stop.get("single_buffer_rationale")))
    if setup.get("setup_validity"):
        plan.append(("Valid for", setup.get("setup_validity")))
    sections.append(render_section("Trade plan", render_fields(plan)))
    reasons = _clean_many(payload.get("reasons"))
    if reasons:
        sections.append(render_section("Why this setup", render_bullets(reasons[:3])))
    semantics = _mapping(payload.get("methodology_selected_entry_semantics"))
    if semantics:
        sections.append(
            render_section(
                "Why This Entry",
                render_fields(
                    (
                        ("Entry type", humanize_code(semantics.get("selected_kind"))),
                        ("Executable now", _yes_no(semantics.get("currently_executable"))),
                        ("Reason", _clean(semantics.get("selection_reason"))),
                    )
                ),
            )
        )
    candles = _mappings(payload.get("methodology_candlestick_evidence"))
    if candles:
        lines = [
            f"{humanize_code(item.get('pattern_id'))}: "
            f"{humanize_code(item.get('pattern_direction'))} • {_clean(item.get('context_note'))}"
            for item in candles[:3]
        ]
        sections.append(render_section("Candlestick Evidence", render_bullets(lines)))
    if pending:
        activation = _activation(setup, focused)
        sections.append(render_section("Activation Required", render_bullets(activation[:4])))
    signal = _signal_snapshot(payload)
    if signal:
        sections.append(signal)
    warnings = _clean_many(setup.get("warnings"))
    target_semantics = _mapping(payload.get("methodology_target_feasibility_semantics"))
    if target_semantics and target_semantics.get("costs_available") is not True:
        warnings = (*warnings, "Displayed targets are gross; fees and slippage are not included.")
    if warnings:
        sections.append(render_section("Main risks", render_bullets(warnings[:4])))
    alternatives = _mappings(setup.get("alternative_entry_opportunities"))
    if alternatives:
        lines = [
            f"{_price_range(item.get('lower'), item.get('upper'))} • preferred "
            f"{format_price(item.get('preferred'))}"
            for item in alternatives[:3]
        ]
        sections.append(render_section("Alternative Entry Opportunities", render_bullets(lines)))
    opportunity_map = opportunity_map_lines(payload)
    if opportunity_map:
        sections.append(render_section("Opportunity map", render_bullets(opportunity_map)))

    timeframe_map = multi_timeframe_lines(payload)
    if timeframe_map:
        sections.append(render_section("Multi-timeframe map", render_bullets(timeframe_map)))

    rationale = rationale_lines(payload, setup)
    if rationale:
        sections.append(
            render_section(
                "Entry, stop, target, and chase rationale",
                render_bullets(rationale),
            )
        )

    evidence = evidence_contradiction_lines(payload, setup)
    if evidence:
        sections.append(render_section("Evidence and contradictions", render_bullets(evidence)))

    diagnostics = diagnostic_summary_lines(payload)
    if diagnostics and explain:
        sections.append(
            render_section(
                "Diagnostics • Collision, runner, and lifecycle",
                render_bullets(diagnostics),
            )
        )

    rejected = rejected_candidate_lines(payload)
    if rejected and explain:
        sections.append(render_section("Rejected candidates", render_bullets(rejected)))

    if explain:
        sections.extend(_setup_explanation(payload, setup, focused))
    return sections


def _market_context(focused: Mapping[str, object]) -> str:
    outlook = _mapping(focused.get("market_outlook"))
    if not outlook:
        return ""
    return render_section(
        "Market Outlook",
        render_fields(
            (
                ("Regime", humanize_code(outlook.get("regime"))),
                ("Structure", humanize_code(outlook.get("primary_structure"))),
                ("Volatility", humanize_code(outlook.get("volatility"))),
                ("Participation", humanize_code(outlook.get("participation"))),
                ("Price location", _clean(outlook.get("current_location"))),
            )
        ),
    )


def _signal_snapshot(payload: Mapping[str, object]) -> str:
    intelligence = _mapping(payload.get("market_intelligence"))
    warning = _mapping(intelligence.get("early_warning"))
    edge = _mapping(payload.get("historical_edge"))
    fields: list[tuple[str, object]] = []
    if warning:
        evidence = _clean_many(warning.get("evidence"))
        concerns = _clean_many(warning.get("concerns"))
        warning_state = humanize_code(warning.get("state"))
        direction = humanize_code(warning.get("direction"))
        if direction == UNAVAILABLE:
            direction = "No clear lean"
        fallback_concern = (
            "Evidence does not agree on direction"
            if "contradictory" in warning_state.lower()
            else "No major conflict detected"
        )
        fields.extend(
            (
                ("Early warning", warning_state),
                ("Directional lean", direction),
                ("Main evidence", evidence[0] if evidence else UNAVAILABLE),
                ("Main concern", concerns[0] if concerns else fallback_concern),
            )
        )
    if edge:
        expected_r = edge.get("expected_r")
        fields.extend(
            (
                (
                    "Historical edge",
                    "Validated" if edge.get("available") is True else "Not validated yet",
                ),
                (
                    "Expected return",
                    f"{float(expected_r):+.2f}R"
                    if isinstance(expected_r, int | float)
                    else UNAVAILABLE,
                ),
                ("Model note", _clean(edge.get("reason"))),
            )
        )
    return render_section("Signal snapshot", render_fields(fields)) if fields else ""


def _side_explanation(
    focused: Mapping[str, object],
    *,
    include_blockers: bool = True,
) -> list[str]:
    sections: list[str] = []
    for label, key in (("Long Assessment", "long_thesis"), ("Short Assessment", "short_thesis")):
        thesis = _mapping(focused.get(key))
        if not thesis:
            continue
        blockers = _clean_many(thesis.get("blockers"))
        body = render_fields(
            (
                ("State", humanize_code(thesis.get("state"))),
                ("Best strategy", humanize_code(thesis.get("primary_strategy"))),
                ("Quality", _quality(thesis.get("score"))),
                ("Required threshold", _quality(thesis.get("approval_threshold"))),
                ("Summary", _clean(thesis.get("summary"))),
            )
        )
        if blockers and include_blockers:
            body += "\n\n" + render_bullets(blockers[:4])
        sections.append(render_section(label, body))
    return sections


def _setup_explanation(
    payload: Mapping[str, object],
    setup: Mapping[str, object],
    focused: Mapping[str, object],
) -> list[str]:
    sections: list[str] = []
    quality = _mapping(setup.get("quality_dimensions"))
    if quality:
        sections.append(
            render_section(
                "Quality breakdown",
                render_fields(
                    (
                        ("Setup", _quality(quality.get("setup_quality"))),
                        ("Execution", _quality(quality.get("execution_quality"))),
                        ("Targets", _quality(quality.get("target_quality"))),
                        ("Risk", _quality(quality.get("risk_quality"))),
                        ("Overall", _quality(quality.get("overall_trade_quality"))),
                    )
                ),
            )
        )
    sections.extend(_side_explanation(focused))
    return sections


def _scan_group(
    title: str,
    hint: str,
    items: Sequence[Mapping[str, object]],
) -> str:
    cards = [_scan_card(item, index=index) for index, item in enumerate(items, start=1)]
    body = f"  {hint}\n\n" + ("\n  " + "·" * 72 + "\n\n").join(cards)
    return render_section(f"{title} ({len(items)})", body)


def _scan_card(payload: Mapping[str, object], *, index: int) -> str:
    symbol = str(payload.get("symbol") or "Unknown market")
    selected = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    setup = selected or developing
    if not setup:
        reasons = _clean_many(payload.get("reasons"))
        return "\n".join(
            (
                f"▶  #{index}  {symbol}  •  NO TRADE",
                render_fields((("Why", reasons[0] if reasons else "No valid setup formed"),)),
            )
        )
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    activation = _activation(setup, {})
    quality = _mapping(setup.get("quality_dimensions"))
    initial_rr = setup.get("initial_risk_reward")
    if initial_rr is None and targets:
        initial_rr = targets[0].get("risk_reward")
    runner_rr = setup.get("runner_risk_reward")
    if runner_rr is None and targets:
        runner_rr = targets[-1].get("risk_reward")
    warning = data_quality_warning(payload)
    fields: list[tuple[str, object]] = [
        ("Side", humanize_code(setup.get("direction"))),
        ("Strategy", humanize_code(setup.get("strategy"))),
        ("State", humanize_code(setup.get("entry_status"))),
        ("Current price", format_price(entry.get("current_price"))),
        ("Entry distance", entry_distance_label(setup) or UNAVAILABLE),
        ("Entry zone", _price_range(entry.get("lower"), entry.get("upper"))),
        ("Ideal entry", format_price(entry.get("preferred"))),
        ("Maximum chase", format_price(entry.get("maximum_chase_price"))),
        ("Stop", format_price(stop.get("price"))),
        ("TP1 RR", format_ratio(initial_rr)),
        ("Runner RR", format_ratio(runner_rr)),
        (
            "Setup / execution",
            f"{_quality(quality.get('setup_quality') or setup.get('confidence_score'))} / "
            f"{_quality(quality.get('execution_quality'))}",
        ),
        ("Continuation", _quality(quality.get("continuation_quality"))),
        (
            "Alignment",
            humanize_code(
                setup.get("alignment_classification") or setup.get("trend_classification")
            ),
        ),
    ]
    evidence = _clean_many(setup.get("evidence"))
    warnings = _clean_many(setup.get("warnings"))
    if evidence:
        fields.append(("Evidence", evidence[0]))
    if warnings:
        fields.append(("Main risk", warnings[0]))
    if warning:
        fields.append(("Data quality", warning))
    if targets:
        fields.append(
            ("Targets", "  /  ".join(format_price(item.get("price")) for item in targets[:3]))
        )
    if developing and not selected:
        fields.append(("Wait for", activation[0] if activation else "Entry confirmation"))
    fields.append(("Inspect", f"apex analyze {symbol.replace('/', '')}"))
    return "\n".join((f"▶  #{index}  {symbol}", render_fields(fields)))


def _watch_items(focused: Mapping[str, object]) -> tuple[str, ...]:
    watch = list(_clean_many(focused.get("watch_plan")))
    if not watch:
        for key in ("long_thesis", "short_thesis"):
            watch.extend(_clean_many(_mapping(focused.get(key)).get("activation_conditions")))
    return tuple(dict.fromkeys(watch))


def _activation(
    setup: Mapping[str, object],
    focused: Mapping[str, object],
) -> tuple[str, ...]:
    warnings = _clean_many(setup.get("warnings"))
    useful = tuple(
        item
        for item in warnings
        if any(
            word in item.lower() for word in ("confirm", "retest", "reclaim", "pullback", "close")
        )
    )
    return useful or _watch_items(focused) or ("Wait for all entry checks to confirm.",)


def _screening_lanes(screening: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = []
    for candidate in _mappings(screening.get("candidates"))[:8]:
        lanes = _mappings(candidate.get("discovery_lanes"))
        if lanes:
            lane = lanes[0]
            lines.append(
                f"{candidate.get('symbol')}: {humanize_code(lane.get('lane'))} "
                f"({_quality(lane.get('score'))}) — {_clean(lane.get('reason'))}"
            )
    return tuple(lines)


def _clean(value: object) -> str:
    if value is None:
        return UNAVAILABLE
    text = str(value).strip()
    replacements = (
        (
            r"all candidates scored below their configured approval thresholds",
            "No setup reached the minimum quality required for a trade.",
        ),
        (
            r"all candidates were rejected by deterministic candidate-selection rules",
            "No setup passed the current quality and execution checks.",
        ),
        (
            r"historical edge unavailable: artifact missing",
            "No validated historical model is available yet.",
        ),
        (
            r"active-candle evidence is provisional",
            "Wait for the current candle to close and confirm.",
        ),
        (
            r"rule-based quality is below the configured approval threshold",
            "Setup quality is below the required level.",
        ),
        (
            r"score [\d.]+ is below aggressive floor [\d.]+",
            "Setup quality is below the minimum required level.",
        ),
        (
            r"current price is technically valid and immediately actionable",
            "Price is near the trigger area, but remaining checks must pass.",
        ),
        (
            r"no coherent early-warning matrix is active",
            "No clear early-warning pattern is active.",
        ),
        (
            r"no (long|short) candidate passed strategy generation",
            r"No clear \1 setup formed.",
        ),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(
        r";?\s*cross-sectional raw score\s+[-+\d.]+",
        "",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"(?<![\w.])-?\d+\.\d{7,}", _short_number, text)
    return text[:1].upper() + text[1:] if text else UNAVAILABLE


def _short_number(match: re.Match[str]) -> str:
    number = float(match.group(0))
    absolute = abs(number)
    decimals = 2 if absolute >= 1_000 else 4 if absolute >= 1 else 6 if absolute >= 0.01 else 8
    return f"{number:,.{decimals}f}"


def _clean_many(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(dict.fromkeys(_clean(item) for item in value))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _price_range(low: object, high: object) -> str:
    if low is None and high is None:
        return UNAVAILABLE
    if low == high or high is None:
        return format_price(low)
    if low is None:
        return format_price(high)
    return f"{format_price(low)} - {format_price(high)}"


def _quality(value: object) -> str:
    score = format_score(value)
    return score if score == UNAVAILABLE else f"{score}/100"


def _yes_no(value: object) -> str:
    return "Yes" if value is True else "No" if value is False else UNAVAILABLE


def _count(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 0
    return 0


__all__ = ["render_analysis", "render_scan"]
