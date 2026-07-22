"""Trade-first terminal output for Apex scan and selected-symbol analysis."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime

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
    canonical_actionability_label,
    canonical_actionability_state,
    data_quality_warning,
    diagnostic_summary_lines,
    evidence_contradiction_lines,
    multi_timeframe_lines,
    opportunity_map_lines,
    partition_scan_results,
    rationale_lines,
    rejected_candidate_lines,
)
from apex.presentation.scan_groups import flatten_existing_scan_groups


def render_analysis(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render one selected market as an actionable portfolio or clear no-trade plan."""

    symbol = str(payload.get("symbol") or "Unknown market")
    focused = _mapping(payload.get("focused_analysis"))
    portfolio = _mapping(payload.get("opportunity_portfolio"))
    sections = [render_title(f"Apex Analysis • {symbol}")]

    if portfolio:
        sections.extend(_portfolio_analysis_sections(payload, portfolio, focused, explain=explain))
        return "\n\n".join(section for section in sections if section)

    selected = _mapping(payload.get("setup"))
    developing = _mapping(payload.get("developing_setup"))
    setup = selected or developing
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


def _portfolio_analysis_sections(
    payload: Mapping[str, object],
    portfolio: Mapping[str, object],
    focused: Mapping[str, object],
    *,
    explain: bool,
) -> list[str]:
    current = _mappings(portfolio.get("current_opportunities"))
    nearby = _mappings(portfolio.get("nearby_opportunities"))
    follow_up = _mappings(portfolio.get("follow_up_opportunities"))
    runner = _mappings(portfolio.get("runner_opportunities"))
    all_opportunities = _mappings(portfolio.get("opportunities"))
    symbol = str(portfolio.get("symbol") or payload.get("symbol") or "Unknown market")

    sections = [_portfolio_market_snapshot(payload, portfolio)]
    if current:
        sections.append(
            _opportunity_group(
                "Current opportunities",
                current,
                symbol=symbol,
                generated_at=payload.get("generated_at"),
            )
        )
    if nearby:
        sections.append(
            _opportunity_group(
                "Conditional monitoring",
                nearby,
                symbol=symbol,
                generated_at=payload.get("generated_at"),
            )
        )
    if follow_up:
        sections.append(
            _opportunity_group(
                "Follow-up opportunity",
                follow_up,
                symbol=symbol,
                generated_at=payload.get("generated_at"),
            )
        )
    if runner:
        sections.append(
            _opportunity_group(
                "Runner management",
                runner,
                symbol=symbol,
                generated_at=payload.get("generated_at"),
            )
        )

    if not all_opportunities:
        setup_plan = _setup_plan_section(payload)
        if setup_plan:
            sections.append(setup_plan)
        context = _market_context(focused)
        if context:
            sections.append(context)
        risk = _risk_and_invalidation_section(payload)
        if risk:
            sections.append(risk)
        if explain:
            sections.extend(_canonical_explain_sections(payload, ()))
        return sections

    setup_plan = _setup_plan_section(payload)
    if setup_plan:
        sections.append(setup_plan)
    context = _market_context(focused)
    if context:
        sections.append(context)

    if explain:
        sections.extend(_canonical_explain_sections(payload, all_opportunities))
    return sections


def _portfolio_market_snapshot(
    payload: Mapping[str, object],
    portfolio: Mapping[str, object],
) -> str:
    verdict = _mapping(payload.get("methodology_verdict"))
    fields: list[tuple[str, object]] = [
        ("CMP", format_price(portfolio.get("cmp"))),
        ("Portfolio decision", humanize_code(portfolio.get("decision"))),
        ("Analysis mode", humanize_code(portfolio.get("analysis_mode"))),
        ("Opportunities", portfolio.get("opportunity_count")),
        ("Methodology verdict", humanize_code(verdict.get("status"))),
    ]
    if not _mappings(portfolio.get("opportunities")):
        signal_time = _signal_generated_label(payload.get("generated_at"))
        if signal_time:
            fields.insert(1, ("Signal generated", signal_time))
    return render_section(
        "Market snapshot",
        render_fields(fields),
    )


def _opportunity_group(
    title: str,
    opportunities: Sequence[Mapping[str, object]],
    *,
    symbol: str,
    generated_at: object = None,
) -> str:
    cards = [
        _opportunity_card(
            opportunity,
            index=index,
            symbol=symbol,
            generated_at=generated_at,
        )
        for index, opportunity in enumerate(opportunities, start=1)
    ]
    return render_section(title, ("\n  " + "·" * 72 + "\n\n").join(cards))


def _opportunity_card(
    opportunity: Mapping[str, object],
    *,
    index: int,
    symbol: str,
    generated_at: object = None,
) -> str:
    setup = _mapping(opportunity.get("setup")) or opportunity
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    quality = _mapping(setup.get("quality_dimensions"))
    reference = _number(entry.get("preferred")) or _number(entry.get("current_price"))
    direction = humanize_code(opportunity.get("direction") or setup.get("direction")).upper()
    entry_fields: list[tuple[str, object]] = [
        ("CMP", format_price(entry.get("current_price"))),
        ("Ideal entry", format_price(entry.get("preferred"))),
        ("Entry range", _price_range(entry.get("lower"), entry.get("upper"))),
        ("Maximum chase", format_price(entry.get("maximum_chase_price"))),
    ]
    target_fields: list[tuple[str, object]] = []
    for target_index, target in enumerate(targets[:3], start=1):
        target_fields.append(
            (
                f"TP{target_index}",
                _target_label(
                    target,
                    reference=reference,
                    target_quality=quality.get("target_quality") if target_index == 1 else None,
                ),
            )
        )
    activation_fields = _conditional_opportunity_fields(setup)
    quality_fields = (
        *_opportunity_execution_fields(setup),
        *_opportunity_htf_fields(setup),
        *_opportunity_quality_fields(opportunity, setup, quality),
    )
    warning_fields: list[tuple[str, object]] = []
    warnings = _clean_many(setup.get("warnings"))
    if warnings:
        warning_fields.append(("Main risk", warnings[0]))

    header_lines = [f"▶  Opportunity #{index}  {symbol} — {direction}"]
    signal_time = _signal_generated_label(generated_at)
    if signal_time:
        header_lines.append(f"   Signal generated  {signal_time}")
    header_lines.append(f"   {_opportunity_context_line(opportunity, setup)}")
    relationship_line = _opportunity_relationship_line(setup)
    if relationship_line:
        header_lines.append(f"   {relationship_line}")
    return "\n".join(
        (
            *header_lines,
            "",
            _opportunity_detail_blocks(
                entry_fields=entry_fields,
                risk_fields=(("Stop loss", _price_with_move(stop.get("price"), reference)),),
                target_fields=target_fields,
                activation_fields=activation_fields,
                quality_fields=quality_fields,
                warning_fields=warning_fields,
            ),
        )
    )


def _conditional_opportunity_fields(
    setup: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    plan = _mapping(setup.get("conditional_plan"))
    if not plan:
        return ()

    trigger = _mapping(plan.get("trigger"))
    invalidation = _mapping(plan.get("pre_entry_invalidation"))
    expiry = _mapping(plan.get("expiry"))
    trigger_type = trigger.get("type") or trigger.get("kind")

    fields: list[tuple[str, object]] = [
        (
            "Activation trigger",
            f"{humanize_code(trigger_type)} at {format_price(trigger.get('level'))}",
        ),
        ("Trigger condition", trigger.get("condition")),
        ("Pre-entry invalidation", format_price(invalidation.get("price"))),
        ("Order intent", humanize_code(plan.get("recommended_order_intent"))),
        (
            "Resting order authorized",
            "Yes" if plan.get("conditional_order_eligible") is True else "No",
        ),
    ]
    if expiry.get("validity"):
        fields.append(("Conditional validity", expiry.get("validity")))
    if expiry.get("reason"):
        fields.append(("Conditional expiry reason", expiry.get("reason")))
    elif setup.get("setup_expiry_reason"):
        fields.append(("Conditional expiry reason", setup.get("setup_expiry_reason")))
    return tuple(fields)


def _opportunity_execution_fields(
    setup: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    state = canonical_actionability_state(setup)
    conditional = _mapping(setup.get("conditional_plan"))
    execution_allowed = setup.get("execution_allowed_now") is True

    if state in {"INVALIDATED", "invalidated"}:
        availability = "Invalidated"
    elif state in {"MISSED_OR_CHASING", "missed_or_chasing"}:
        availability = "Missed or chasing"
    elif execution_allowed:
        availability = "Executable now"
    elif conditional:
        availability = "Future setup - activation required"
    else:
        availability = "Valid setup - not executable now"

    reason = (
        setup.get("execution_block_reason")
        or setup.get("execution_reason")
        or setup.get("actionability_reason")
        or setup.get("entry_status_reason")
    )
    if reason is None and conditional:
        trigger = _mapping(conditional.get("trigger"))
        reason = trigger.get("condition") or "the stated activation trigger has not completed"
    if reason is None and not execution_allowed:
        reason = "current execution is not authorized by the canonical actionability state"

    fields: list[tuple[str, object]] = [
        ("Setup availability", availability),
        ("Execution authorized now", "Yes" if execution_allowed else "No"),
    ]
    if reason is not None:
        fields.append(("Execution reason", reason))
    return tuple(fields)


def _opportunity_htf_fields(
    setup: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    consequence = _mapping(setup.get("htf_consequence"))
    if not consequence:
        methodology = _mapping(setup.get("methodology"))
        consequence = _mapping(methodology.get("htf_consequence"))
    if not consequence:
        evaluation = _mapping(setup.get("strategy_evaluation"))
        consequence = _mapping(evaluation.get("htf_consequence"))
    if not consequence:
        return ()

    fields: list[tuple[str, object]] = []
    treatment = consequence.get("execution_treatment")
    severity = consequence.get("severity")
    if treatment is not None:
        fields.append(("HTF treatment", humanize_code(treatment)))
    if severity is not None:
        fields.append(("HTF severity", humanize_code(severity)))
    penalty = _number(consequence.get("score_penalty_points"))
    if penalty is not None and penalty > 0.0:
        fields.append(("HTF score penalty", f"{penalty:g} points"))
    return tuple(fields)


def _opportunity_detail_blocks(
    *,
    entry_fields: Sequence[tuple[str, object]],
    risk_fields: Sequence[tuple[str, object]],
    target_fields: Sequence[tuple[str, object]],
    activation_fields: Sequence[tuple[str, object]],
    quality_fields: Sequence[tuple[str, object]],
    warning_fields: Sequence[tuple[str, object]],
) -> str:
    blocks: list[str] = []
    for title, fields in (
        ("ENTRY", entry_fields),
        ("RISK", risk_fields),
        ("TARGETS", target_fields),
        ("ACTIVATION", activation_fields),
        ("QUALITY", quality_fields),
        ("CAUTION", warning_fields),
    ):
        if fields:
            blocks.append(f"  {title}\n{render_fields(fields, indent=4)}")
    return "\n\n".join(blocks)


def _actionability_label(setup: Mapping[str, object]) -> str:
    state = canonical_actionability_state(setup)
    if state:
        return humanize_code(state)
    return canonical_actionability_label(setup)


def _entry_field(entry: Mapping[str, object]) -> tuple[str, object]:
    lower = _number(entry.get("lower"))
    upper = _number(entry.get("upper"))
    if lower is not None and upper is not None and lower == upper:
        return ("Entry price", format_price(lower))
    return ("Entry zone", _price_range(entry.get("lower"), entry.get("upper")))


def _setup_plan_section(payload: Mapping[str, object]) -> str:
    plan = _mapping(payload.get("setup_plan"))
    if not plan:
        return ""
    if plan.get("geometry_available") is True:
        return render_section(
            "Setup plan",
            render_fields(
                (
                    ("Status", humanize_code(plan.get("status"))),
                    ("Opportunities", plan.get("opportunity_count")),
                )
            ),
        )
    return render_section(
        "Setup plan",
        render_fields(
            (
                ("Status", "NO VALID SETUP YET"),
                ("Current state", plan.get("current_state")),
                ("Long trigger", plan.get("long_trigger")),
                ("Short trigger", plan.get("short_trigger")),
                ("Invalidation", plan.get("invalidation")),
                ("Stop", plan.get("stop")),
                ("Main risk", plan.get("main_risk")),
            )
        ),
    )


def _risk_and_invalidation_section(payload: Mapping[str, object]) -> str:
    plan = _mapping(payload.get("setup_plan"))
    if not plan:
        return ""

    invalidation = plan.get("invalidation")
    stop = plan.get("stop")
    has_invalidation = invalidation not in {None, "", UNAVAILABLE}
    has_stop = stop not in {None, "", UNAVAILABLE}
    if not has_invalidation and not has_stop:
        return ""

    fields: list[tuple[str, object]] = []
    if has_invalidation:
        fields.append(("Invalidation", invalidation))
    if has_stop:
        fields.append(("Stop", stop))

    main_risk = plan.get("main_risk")
    if main_risk not in {None, "", UNAVAILABLE}:
        fields.append(("Main risk", main_risk))
    return render_section("Risk and invalidation", render_fields(fields))


def render_scan(payload: Mapping[str, object], *, explain: bool = False) -> str:
    """Render every displayed canonical scan opportunity and truthful setup plan."""

    groups = _canonical_scan_groups(payload)
    sections = [render_title("Apex Market Scan")]
    sections.append(_scan_summary(payload, groups))
    health = _scan_health_summary(groups)
    if health:
        sections.append(health)

    for title, hint, items in (
        (
            "Enter at CMP",
            "CMP is inside an executable entry area.",
            groups["enter"],
        ),
        (
            "Confirmation entry",
            "Price location is usable after the stated micro confirmation.",
            groups["confirmation"],
        ),
        (
            "Conditional monitoring",
            "A setup exists near CMP; do not enter until its stated trigger completes.",
            groups["nearby"],
        ),
        (
            "Developing / follow-up",
            "These plans remain valid but are not executable yet.",
            groups["developing"],
        ),
    ):
        if items:
            sections.append(_canonical_scan_group(title, hint, items))

    if groups["no_trade"]:
        sections.append(_no_trade_plan_group(groups["no_trade"]))

    truncation = _scan_truncation_lines(payload)
    if truncation:
        sections.append(render_section("Display limits", render_bullets(truncation)))

    failures = _scan_failure_lines(payload)
    if failures:
        sections.append(render_section("Scan failures", render_bullets(failures)))

    conclusion = _scan_conclusion(groups)
    if conclusion:
        sections.append(conclusion)

    if explain:
        screening = _mapping(payload.get("screening"))
        lanes = _screening_lanes(screening)
        if lanes:
            sections.append(render_section("Shortlist evidence", render_bullets(lanes)))
        sections.extend(_scan_explain_sections(payload))

    return "\n\n".join(section for section in sections if section)


def _scan_summary(
    payload: Mapping[str, object],
    groups: Mapping[str, Sequence[Mapping[str, object]]],
) -> str:
    failure_count = len(_mapping(payload.get("failures")))
    methodology = _scan_methodology_status(payload)
    screening = _mapping(payload.get("screening"))
    discovered = screening.get("total_contracts") or payload.get("attempted_symbol_count")
    screened = screening.get("candle_screened_count") or payload.get("attempted_symbol_count")
    shortlisted = screening.get("shortlisted_count") or payload.get("attempted_symbol_count")
    return render_section(
        "Scan summary",
        render_fields(
            (
                ("Markets discovered", discovered),
                ("Markets screened", screened),
                ("Symbols shortlisted", shortlisted),
                ("Symbols analyzed", payload.get("total_analysis_count")),
                ("Symbols displayed", payload.get("displayed_symbol_count")),
                ("Symbols failed", failure_count),
                ("Opportunities retained", payload.get("retained_opportunity_count")),
                ("Opportunities displayed", payload.get("displayed_opportunity_count")),
                ("Executable now", len(groups["enter"])),
                ("Confirmation entries", len(groups["confirmation"])),
                ("Nearby entries", len(groups["nearby"])),
                ("Developing / follow-up", len(groups["developing"])),
                ("No current trade", len(groups["no_trade"])),
                ("Direction filter", humanize_code(payload.get("direction_filter"))),
                ("Methodology gate", methodology),
            )
        ),
    )


def _canonical_scan_groups(
    payload: Mapping[str, object],
) -> dict[str, list[Mapping[str, object]]]:
    groups: dict[str, list[Mapping[str, object]]] = {
        "enter": [],
        "confirmation": [],
        "nearby": [],
        "developing": [],
        "no_trade": [],
    }
    results = _mappings(payload.get("results"))

    # Preserve the established renderer for payloads that predate the
    # canonical opportunity portfolio.
    if not results or not any(_mapping(result.get("opportunity_portfolio")) for result in results):
        return _legacy_scan_groups(payload)

    for result in results:
        portfolio = _mapping(result.get("opportunity_portfolio"))
        if not portfolio:
            selected = _mapping(result.get("setup"))
            developing = _mapping(result.get("developing_setup"))
            setup = selected or developing
            if not setup:
                groups["no_trade"].append(result)
                continue

            canonical_state = canonical_actionability_state(setup).strip().lower()
            entry_state = str(setup.get("entry_status") or "").strip().lower()
            states = {canonical_state, entry_state}

            if selected and states & {
                "execute_now",
                "aggressive_now",
                "ready_now",
            }:
                groups["enter"].append(result)
            elif selected and states & {
                "execute_on_micro_confirmation",
                "wait_for_retest",
                "wait_for_reclaim",
            }:
                groups["confirmation"].append(result)
            elif selected:
                groups["nearby"].append(result)
            else:
                groups["developing"].append(result)
            continue

        symbol = str(result.get("symbol") or portfolio.get("symbol") or "Unknown market")
        opportunities = _mappings(portfolio.get("opportunities"))
        if not opportunities:
            groups["no_trade"].append(result)
            continue

        for opportunity in opportunities:
            item = {
                "symbol": symbol,
                "opportunity": opportunity,
                "source": result,
            }
            category = (
                str(opportunity.get("category") or opportunity.get("sequence_role") or "")
                .strip()
                .lower()
            )
            setup = _mapping(opportunity.get("setup")) or opportunity
            canonical_state = canonical_actionability_state(setup).strip().lower()
            entry_state = (
                str(opportunity.get("entry_status") or setup.get("entry_status") or "")
                .strip()
                .lower()
            )
            states = {canonical_state, entry_state}

            if category == "current" and states & {
                "execute_now",
                "aggressive_now",
                "ready_now",
            }:
                groups["enter"].append(item)
            elif category == "current" and states & {
                "execute_on_micro_confirmation",
                "wait_for_retest",
                "wait_for_reclaim",
            }:
                groups["confirmation"].append(item)
            elif category == "nearby" or category == "current":
                groups["nearby"].append(item)
            else:
                groups["developing"].append(item)
    return groups


def _legacy_scan_groups(payload: Mapping[str, object]) -> dict[str, list[Mapping[str, object]]]:
    grouped = partition_scan_results(flatten_existing_scan_groups(payload))
    return {
        "enter": list(grouped.actionable_cmp),
        "confirmation": list(grouped.micro_confirmation),
        "nearby": list(grouped.nearby_limit),
        "developing": list(grouped.follow_up_reversal),
        "no_trade": list(grouped.weak_invalid),
    }


def _canonical_scan_group(
    title: str,
    hint: str,
    items: Sequence[Mapping[str, object]],
) -> str:
    cards = [_canonical_scan_card(item, index=index) for index, item in enumerate(items, start=1)]
    body = f"  {hint}\n\n" + ("\n  " + "·" * 72 + "\n\n").join(cards)
    return render_section(f"{title} ({len(items)})", body)


def _canonical_scan_card(item: Mapping[str, object], *, index: int) -> str:
    opportunity = _mapping(item.get("opportunity"))
    if not opportunity:
        return _scan_card(item, index=index)
    source = _mapping(item.get("source"))
    setup = _mapping(opportunity.get("setup")) or opportunity
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    quality = _mapping(setup.get("quality_dimensions"))
    preferred = _number(entry.get("preferred"))
    reference = preferred or _number(entry.get("current_price"))
    symbol = str(item.get("symbol") or source.get("symbol") or "Unknown market")
    direction = humanize_code(opportunity.get("direction") or setup.get("direction"))
    entry_fields: list[tuple[str, object]] = [
        ("CMP", format_price(entry.get("current_price"))),
        ("Ideal entry", format_price(entry.get("preferred"))),
        ("Entry range", _price_range(entry.get("lower"), entry.get("upper"))),
        ("Maximum chase", format_price(entry.get("maximum_chase_price"))),
    ]
    target_fields: list[tuple[str, object]] = []
    for target_index, target in enumerate(targets[:3], start=1):
        target_fields.append(
            (
                f"TP{target_index}",
                _target_label(
                    target,
                    reference=reference,
                    target_quality=quality.get("target_quality") if target_index == 1 else None,
                ),
            )
        )
    activation_fields = _conditional_opportunity_fields(setup)
    quality_fields = (
        *_opportunity_execution_fields(setup),
        *_opportunity_htf_fields(setup),
        *_opportunity_quality_fields(opportunity, setup, quality),
    )
    warning_fields: list[tuple[str, object]] = []
    warnings = _clean_many(setup.get("warnings"))
    if warnings:
        warning_fields.append(("Main risk", warnings[0]))
    data_warning = data_quality_warning(source)
    if data_warning:
        warning_fields.append(("Data warning", data_warning))

    display_rank = source.get("display_rank")
    rank_label = (
        f"Rank #{display_rank}"
        if isinstance(display_rank, int) and not isinstance(display_rank, bool)
        else f"Opportunity #{index}"
    )
    header_lines = [f"▶  {rank_label}  {symbol} — {direction.upper()}"]
    signal_time = _signal_generated_label(source.get("generated_at"))
    if signal_time:
        header_lines.append(f"   Signal generated  {signal_time}")
    header_lines.append(f"   {_opportunity_context_line(opportunity, setup)}")
    relationship_line = _opportunity_relationship_line(setup)
    if relationship_line:
        header_lines.append(f"   {relationship_line}")
    return "\n".join(
        (
            *header_lines,
            "",
            _opportunity_detail_blocks(
                entry_fields=entry_fields,
                risk_fields=(("Stop loss", _price_with_move(stop.get("price"), reference)),),
                target_fields=target_fields,
                activation_fields=activation_fields,
                quality_fields=quality_fields,
                warning_fields=warning_fields,
            ),
        )
    )


def _opportunity_context_line(
    opportunity: Mapping[str, object],
    setup: Mapping[str, object],
) -> str:
    strategy = humanize_code(opportunity.get("strategy") or setup.get("strategy"))
    lane = humanize_code(
        opportunity.get("lane")
        or opportunity.get("effective_lane")
        or opportunity.get("category")
        or opportunity.get("sequence_role")
    )
    actionability = _actionability_label(setup)
    if setup.get("confirmation_required") is True and setup.get("confirmation_complete") is False:
        actionability = "Awaiting trigger"
    return " · ".join(
        value for value in (strategy, lane, actionability) if value and value != UNAVAILABLE
    )


def _signal_generated_label(value: object) -> str | None:
    """Render the immutable analysis timestamp without hiding its timezone."""

    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        timestamp = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return raw
    timezone = timestamp.strftime("%Z")
    if not timezone and timestamp.utcoffset() is not None:
        offset = timestamp.strftime("%z")
        timezone = f"UTC{offset[:3]}:{offset[3:]}" if offset != "+0000" else "UTC"
    return f"{timestamp:%Y-%m-%d %H:%M:%S} {timezone}".rstrip()


def _opportunity_relationship_line(setup: Mapping[str, object]) -> str:
    layered = _mapping(setup.get("layered_state"))
    relationship = humanize_code(layered.get("timeframe_relationship"))
    severity = humanize_code(layered.get("relationship_severity"))
    continuation = humanize_code(
        layered.get("continuation_state") or setup.get("continuation_state")
    )

    relationship_label = relationship
    if (
        relationship
        and relationship != UNAVAILABLE
        and severity
        and severity not in {UNAVAILABLE, "None"}
    ):
        relationship_label = f"{relationship} ({severity.lower()})"

    return " · ".join(
        value for value in (relationship_label, continuation) if value and value != UNAVAILABLE
    )


def _opportunity_quality_fields(
    opportunity: Mapping[str, object],
    setup: Mapping[str, object],
    quality: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    ranking = _mapping(opportunity.get("ranking"))
    fields: list[tuple[str, object]] = []
    values = (
        ("Pattern confidence", quality.get("pattern_confidence")),
        ("Setup quality", quality.get("setup_quality")),
        ("Execution quality", quality.get("execution_quality")),
        ("Target quality", quality.get("target_quality") or quality.get("reward_quality")),
        ("HTF alignment", quality.get("directional_alignment")),
        ("Timing quality", quality.get("timing_quality")),
        ("Data confidence", quality.get("data_confidence")),
        ("Overall trade quality", quality.get("overall_trade_quality")),
        ("Rank score", opportunity.get("rank_score") or ranking.get("rank_score")),
    )
    for label, value in values:
        if value is not None:
            fields.append((label, _quality(value)))

    if not fields:
        fields.append(("Trade quality", _quality(setup.get("confidence_score"))))
    return tuple(fields)


def _signed_move_label(price: float | None, reference: float | None) -> str:
    move = _move_pct(price, reference)
    return UNAVAILABLE if move is None else f"{move:+.2f}%"


def _scan_health_summary(
    groups: Mapping[str, Sequence[Mapping[str, object]]],
) -> str:
    no_trade = groups["no_trade"]
    rejection_counts = Counter(_no_trade_category(item) for item in no_trade)
    fields: list[tuple[str, object]] = [
        ("Executable now", len(groups["enter"])),
        ("Confirmation entries", len(groups["confirmation"])),
        ("Nearby entries", len(groups["nearby"])),
        ("Developing", len(groups["developing"])),
        ("No valid setup", len(no_trade)),
    ]
    for category, count in rejection_counts.most_common(4):
        fields.append((category, count))
    return render_section("Market health", render_fields(fields))


def _no_trade_plan_group(items: Sequence[Mapping[str, object]]) -> str:
    grouped: dict[str, list[Mapping[str, object]]] = {}
    for item in items:
        grouped.setdefault(_no_trade_category(item), []).append(item)

    blocks: list[str] = [
        "  No executable geometry is being invented. Unavailable fields are hidden; "
        "each symbol shows its clearest rejection reason and next action."
    ]
    index = 1
    order = (
        "Waiting for trigger",
        "Weak execution quality",
        "Methodology rejected",
        "No valid structure",
        "Data unavailable",
    )
    for category in order:
        category_items = grouped.get(category, [])
        if not category_items:
            continue
        cards: list[str] = []
        for item in category_items:
            cards.append(_no_trade_plan_card(item, index=index))
            index += 1
        blocks.append(
            f"  {category} ({len(category_items)})\n\n" + ("\n  " + "·" * 72 + "\n\n").join(cards)
        )
    return render_section(f"No current trade — Setup plans ({len(items)})", "\n\n".join(blocks))


def _no_trade_plan_card(payload: Mapping[str, object], *, index: int) -> str:
    symbol = str(payload.get("symbol") or "Unknown market")
    plan = _mapping(payload.get("setup_plan"))
    reason = _no_trade_reason(payload)
    category = _no_trade_category(payload)
    fields: list[tuple[str, object]] = [
        ("Verdict", category),
        ("Reason", reason),
        ("Priority", _no_trade_priority(payload)),
    ]
    for label, value in (
        ("Long trigger", plan.get("long_trigger")),
        ("Short trigger", plan.get("short_trigger")),
        ("Invalidation", plan.get("invalidation")),
    ):
        if _available_output_value(value):
            fields.append((label, value))
    fields.append(("Next action", _no_trade_next_action(payload)))
    return "\n".join(
        (
            f"▶  #{index}  {symbol} — NO VALID SETUP YET · {category.upper()}",
            render_fields(fields),
        )
    )


def _no_trade_reason(payload: Mapping[str, object]) -> str:
    plan = _mapping(payload.get("setup_plan"))
    reasons = _clean_many(payload.get("reasons"))
    for value in (
        plan.get("main_risk"),
        reasons[0] if reasons else None,
        plan.get("current_state"),
    ):
        if _available_output_value(value):
            return _clean(value)
    return "No structurally valid opportunity is available."


def _no_trade_category(payload: Mapping[str, object]) -> str:
    plan = _mapping(payload.get("setup_plan"))
    reason = _no_trade_reason(payload).lower()
    state = str(plan.get("current_state") or "").lower()
    trigger_available = any(
        _available_output_value(plan.get(field)) for field in ("long_trigger", "short_trigger")
    )
    if any(token in reason for token in ("candle", "usable candles", "data", "unavailable")):
        return "Data unavailable"
    if trigger_available:
        return "Waiting for trigger"
    if any(token in reason for token in ("score", "quality", "floor", "confidence")):
        return "Weak execution quality"
    if any(
        token in f"{reason} {state}"
        for token in ("methodology", "routing", "eligible", "suppressed", "rejected")
    ):
        return "Methodology rejected"
    return "No valid structure"


def _no_trade_priority(payload: Mapping[str, object]) -> str:
    category = _no_trade_category(payload)
    if category == "Waiting for trigger":
        return "High"
    if category == "Weak execution quality":
        return "Medium"
    return "Low"


def _no_trade_next_action(payload: Mapping[str, object]) -> str:
    category = _no_trade_category(payload)
    plan = _mapping(payload.get("setup_plan"))
    long_trigger = plan.get("long_trigger")
    short_trigger = plan.get("short_trigger")
    if category == "Waiting for trigger":
        if _available_output_value(long_trigger) and _available_output_value(short_trigger):
            return "Monitor the stated long and short triggers."
        if _available_output_value(long_trigger):
            return "Monitor the stated long trigger; do not chase before activation."
        return "Monitor the stated short trigger; do not chase before activation."
    if category == "Weak execution quality":
        return "Ignore until score, execution quality, or risk geometry improves."
    if category == "Methodology rejected":
        return "Wait for structure or regime evidence to change before re-analysis."
    if category == "Data unavailable":
        return "Retry after sufficient market data is available."
    return "Re-run after a material market-structure change."


def _available_output_value(value: object) -> bool:
    if value is None:
        return False
    normalized = str(value).strip().lower()
    return normalized not in {"", "unavailable", "none", "n/a"}


def _scan_conclusion(
    groups: Mapping[str, Sequence[Mapping[str, object]]],
) -> str:
    executable = len(groups["enter"])
    monitor = len(groups["confirmation"]) + len(groups["nearby"]) + len(groups["developing"])
    no_trade = groups["no_trade"]
    rejected = sum(
        _no_trade_category(item) in {"Methodology rejected", "No valid structure"}
        for item in no_trade
    )
    lines = [
        f"Executable setups: {executable}.",
        f"Symbols worth monitoring: {monitor}.",
        f"Rejected until conditions change: {rejected}.",
    ]
    if executable == 0:
        lines.insert(0, "No executable setup was found in this scan.")
    lines.append("Use `apex analyze SYMBOL` for complete multi-opportunity diagnostics.")
    return render_section("Scan conclusion", render_bullets(lines))


def _scan_methodology_status(payload: Mapping[str, object]) -> str:
    statuses = {
        str(_mapping(result.get("methodology_verdict")).get("status"))
        for result in _mappings(payload.get("results"))
        if _mapping(result.get("methodology_verdict")).get("status")
    }
    if not statuses:
        return UNAVAILABLE
    return ", ".join(sorted(humanize_code(status) for status in statuses))


def _scan_truncation_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = []
    filtered = _number(payload.get("filtered_symbol_count"))
    displayed = _number(payload.get("displayed_symbol_count"))
    if filtered is not None and displayed is not None and filtered > displayed:
        lines.append(f"Showing {int(displayed)} of {int(filtered)} filtered symbols.")
    retained = _number(payload.get("retained_opportunity_count"))
    shown = _number(payload.get("displayed_opportunity_count"))
    if retained is not None and shown is not None and retained > shown:
        lines.append(f"Showing {int(shown)} of {int(retained)} retained opportunities.")
    if lines:
        lines.append("Use --output json for the complete structured record.")
    return tuple(lines)


def _scan_failure_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    failures = _mapping(payload.get("failures"))
    return tuple(f"{symbol} — {_clean(reason)}" for symbol, reason in failures.items())


def _canonical_explain_sections(
    payload: Mapping[str, object],
    opportunities: Sequence[Mapping[str, object]],
) -> list[str]:
    """Render truthful diagnostics without changing canonical decisions."""

    sections: list[str] = []
    methodology = _methodology_enforcement_fields(payload, opportunities)
    if methodology:
        sections.append(render_section("Methodology enforcement", render_fields(methodology)))

    portfolio_lines = _canonical_portfolio_lines(opportunities)
    if portfolio_lines:
        sections.append(render_section("Opportunity portfolio", render_bullets(portfolio_lines)))

    timeframe = multi_timeframe_lines(payload)
    if timeframe:
        sections.append(render_section("Multi-timeframe evidence", render_bullets(timeframe)))

    rationale = _canonical_rationale_lines(payload, opportunities)
    if rationale:
        sections.append(
            render_section(
                "Entry, stop, target, and chase rationale",
                render_bullets(rationale),
            )
        )

    evidence = _canonical_evidence_lines(payload, opportunities)
    if evidence:
        sections.append(render_section("Supporting evidence", render_bullets(evidence)))

    contradictions = _canonical_contradiction_lines(payload, opportunities)
    if contradictions:
        sections.append(render_section("Contradictions", render_bullets(contradictions)))

    missing = _missing_evidence_lines(payload)
    if missing:
        sections.append(render_section("Missing evidence", render_bullets(missing)))

    diagnostics = diagnostic_summary_lines(payload)
    if diagnostics:
        sections.append(render_section("Collision and sequence", render_bullets(diagnostics)))

    rejected = tuple(
        dict.fromkeys(
            (
                *rejected_candidate_lines(payload),
                *_methodology_suppressed_candidate_lines(payload),
            )
        )
    )
    if rejected:
        sections.append(
            render_section("Rejected and suppressed candidates", render_bullets(rejected))
        )
        total_rejected = _rejected_candidate_count(payload)
        if total_rejected > len(rejected):
            sections.append(
                render_section(
                    "Explain display limits",
                    render_bullets(
                        (
                            f"Showing {len(rejected)} of {total_rejected} rejected candidates.",
                            "Use --output json for the complete structured record.",
                        )
                    ),
                )
            )

    data_lines = _data_diagnostic_lines(payload)
    if data_lines:
        sections.append(render_section("Data quality", render_bullets(data_lines)))

    tracking = _outcome_tracking_fields(payload)
    if tracking:
        sections.append(render_section("Outcome-tracking status", render_fields(tracking)))

    calibration = _historical_calibration_fields(payload)
    if calibration:
        sections.append(render_section("Historical calibration", render_fields(calibration)))
    return sections


def _methodology_suppressed_candidate_lines(
    payload: Mapping[str, object],
) -> tuple[str, ...]:
    phase5 = _mapping(payload.get("phase5_diagnostics"))
    routing = _mapping(phase5.get("methodology_candidate_routing"))
    lines: list[str] = []
    for item in _mappings(routing.get("suppressed_candidates")):
        strategy = humanize_code(item.get("strategy"))
        direction = humanize_code(item.get("direction"))
        reasons = _clean_many(item.get("reasons"))
        reason_codes = _clean_many(item.get("reason_codes"))
        reason = reasons[0] if reasons else reason_codes[0] if reason_codes else "Suppressed"
        lines.append(f"{strategy} • {direction} — {reason}")
    return tuple(lines)


def _methodology_enforcement_fields(
    payload: Mapping[str, object],
    opportunities: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, object], ...]:
    phase5 = _mapping(payload.get("phase5_diagnostics"))
    summary = (
        _mapping(payload.get("methodology_enforcement"))
        or _mapping(payload.get("methodology_summary"))
        or _mapping(payload.get("methodology_gate_summary"))
        or _mapping(phase5.get("methodology_candidate_routing"))
    )
    statuses = [
        str(_mapping(opportunity.get("methodology_verdict")).get("status")).strip().lower()
        for opportunity in opportunities
        if _mapping(opportunity.get("methodology_verdict")).get("status")
    ]
    decisions = _mappings(summary.get("strategy_decisions"))
    candidate_decisions = tuple(
        item for item in decisions if item.get("candidate_id") not in {None, ""}
    )
    evaluated: object
    allowed: object
    deferred: object
    suppressed: object
    unavailable: object
    if candidate_decisions:
        action_counts = Counter(
            str(item.get("action") or "unavailable").strip().lower() for item in candidate_decisions
        )
        evaluated = summary.get("input_candidate_count") or len(candidate_decisions)
        allowed = action_counts["allow"]
        deferred = action_counts["defer"]
        suppressed = action_counts["suppress"]
        unavailable = max(
            0,
            int(_number(evaluated) or 0) - allowed - deferred - suppressed,
        )
    else:
        evaluated = None
        allowed = None
        deferred = None
        suppressed = None
        unavailable = None
    evaluated = evaluated or (
        summary.get("candidates_evaluated")
        or summary.get("evaluated")
        or summary.get("retained_candidate_count")
    )
    suppressed_count = summary.get("suppressed_candidate_count")
    if evaluated is None and suppressed_count is not None:
        retained_number = _number(summary.get("retained_candidate_count")) or 0.0
        suppressed_number = _number(suppressed_count)
        if suppressed_number is not None:
            evaluated = int(retained_number + suppressed_number)
    if evaluated is None and opportunities:
        evaluated = len(opportunities)
    allowed = summary.get("allowed") if allowed is None else allowed
    if allowed is None:
        allowed = sum(status in {"allowed", "accepted", "approved"} for status in statuses)
    deferred = summary.get("deferred") if deferred is None else deferred
    if deferred is None:
        deferred = sum(status in {"deferred", "wait", "developing"} for status in statuses)
    suppressed = summary.get("suppressed") if suppressed is None else suppressed
    if suppressed is None:
        suppressed = summary.get("suppressed_candidate_count")
    if suppressed is None:
        suppressed = sum(status in {"suppressed", "blocked", "rejected"} for status in statuses)
    unavailable = summary.get("unavailable") if unavailable is None else unavailable
    if unavailable is None:
        unavailable = sum(status == "unavailable" for status in statuses)

    category_counts = tuple(
        _number(value) for value in (allowed, deferred, suppressed, unavailable)
    )
    known_category_total = sum(value for value in category_counts if value is not None)
    evaluated_number = _number(evaluated)
    if evaluated_number is None or evaluated_number < known_category_total:
        evaluated = int(known_category_total)

    gate_mode = (
        summary.get("gate_mode")
        or payload.get("methodology_gate_mode")
        or _mapping(payload.get("configuration")).get("methodology_gate_mode")
    )
    fields = (
        ("Gate mode", humanize_code(gate_mode)),
        ("Candidates evaluated", evaluated),
        ("Allowed", allowed),
        ("Deferred", deferred),
        ("Suppressed", suppressed),
        ("Unavailable", unavailable),
    )
    return fields if any(value not in {None, UNAVAILABLE, ""} for _, value in fields) else ()


def _canonical_portfolio_lines(
    opportunities: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for opportunity in opportunities:
        setup = _mapping(opportunity.get("setup")) or opportunity
        identity = opportunity.get("opportunity_id") or "Unknown opportunity"
        role = humanize_code(opportunity.get("sequence_role") or opportunity.get("category"))
        side = humanize_code(opportunity.get("direction") or setup.get("direction"))
        strategy = humanize_code(opportunity.get("strategy") or setup.get("strategy"))
        action = _actionability_label(setup)
        verdict = humanize_code(_mapping(opportunity.get("methodology_verdict")).get("status"))
        lines.append(f"{identity}: {role} • {side} • {strategy} • {action} • {verdict}")
    return tuple(lines)


def _canonical_rationale_lines(
    payload: Mapping[str, object],
    opportunities: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for opportunity in opportunities:
        setup = _mapping(opportunity.get("setup")) or opportunity
        identity = opportunity.get("opportunity_id") or "Opportunity"
        for line in rationale_lines(payload, setup):
            lines.append(f"{identity} — {line}")
    return tuple(dict.fromkeys(lines))


def _canonical_evidence_lines(
    payload: Mapping[str, object],
    opportunities: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for opportunity in opportunities:
        setup = _mapping(opportunity.get("setup")) or opportunity
        identity = opportunity.get("opportunity_id") or "Opportunity"
        evidence = _clean_many(setup.get("evidence"))
        if not evidence:
            evidence = tuple(
                line.removeprefix("Support: ")
                for line in evidence_contradiction_lines(payload, setup)
                if line.startswith("Support: ")
            )
        lines.extend(f"{identity} — {item}" for item in evidence[:4])
    return tuple(dict.fromkeys(lines))


def _canonical_contradiction_lines(
    payload: Mapping[str, object],
    opportunities: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for opportunity in opportunities:
        setup = _mapping(opportunity.get("setup")) or opportunity
        identity = opportunity.get("opportunity_id") or "Opportunity"
        contradictions = _clean_many(setup.get("contradictions")) or _clean_many(
            setup.get("warnings")
        )
        if not contradictions:
            contradictions = tuple(
                line.removeprefix("Contradiction: ")
                for line in evidence_contradiction_lines(payload, setup)
                if line.startswith("Contradiction: ")
            )
        lines.extend(f"{identity} — {item}" for item in contradictions[:4])
    return tuple(dict.fromkeys(lines))


def _missing_evidence_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    completeness = _mapping(payload.get("methodology_completeness"))
    missing = _clean_many(completeness.get("unavailable_fields"))
    if not missing:
        missing = _clean_many(payload.get("missing_evidence"))
    available = _available_methodology_fields(payload)
    return tuple(
        f"Unavailable: {item}" for item in missing if item.strip().lower() not in available
    )


def _available_methodology_fields(payload: Mapping[str, object]) -> set[str]:
    portfolio = _mapping(payload.get("opportunity_portfolio"))
    opportunities = _mappings(portfolio.get("opportunities"))
    available: set[str] = set()
    for opportunity in opportunities:
        setup = _mapping(opportunity.get("setup")) or opportunity
        if setup.get("confirmation_required") is not None:
            available.add("confirmation_policy")
        if _clean_many(setup.get("warnings")) or _clean_many(setup.get("contradictions")):
            available.add("contradictions")
        if _mapping(setup.get("entry")):
            available.add("entry_opportunities")
        if _mapping(setup.get("stop_loss")):
            available.add("invalidation")
        if _mappings(setup.get("take_profits")):
            available.add("targets")
        if setup.get("setup_expiry_seconds") is not None:
            available.add("duration")
        if setup.get("confidence_score") is not None or _mapping(setup.get("quality_dimensions")):
            available.add("confidence")
    return available


def _rejected_candidate_count(payload: Mapping[str, object]) -> int:
    candidates = (
        _mappings(payload.get("rejected_candidates"))
        or _mappings(payload.get("candidate_rejections"))
        or _mappings(payload.get("rejections"))
    )
    return len(candidates)


def _data_diagnostic_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    lines: list[str] = []
    warning = data_quality_warning(payload)
    if warning:
        lines.append(warning)
    diagnostics = _mapping(payload.get("data_diagnostics")) or _mapping(
        payload.get("market_data_diagnostics")
    )
    for label, key in (
        ("Freshness", "freshness"),
        ("Coverage", "coverage"),
        ("Stale candles", "stale_candles"),
        ("Missing timeframes", "missing_timeframes"),
    ):
        value = diagnostics.get(key)
        if value is None or value == "" or value == () or value == []:
            continue
        lines.append(f"{label}: {value}")
    return tuple(lines)


def _outcome_tracking_fields(
    payload: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    tracking = (
        _mapping(payload.get("outcome_tracking"))
        or _mapping(payload.get("outcome_tracking_status"))
        or _mapping(payload.get("analysis_database"))
    )
    enabled = tracking.get("enabled")
    database = tracking.get("database") or tracking.get("path") or tracking.get("database_path")
    if enabled is None and database is None:
        return ()
    return (
        (
            "Outcome tracking",
            "Enabled" if enabled is True else "Disabled" if enabled is False else enabled,
        ),
        ("Database", database),
    )


def _historical_calibration_fields(
    payload: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    calibration = (
        _mapping(payload.get("historical_calibration"))
        or _mapping(payload.get("historical_edge"))
        or _mapping(payload.get("calibration"))
    )
    if not calibration:
        return ()
    available = calibration.get("available")
    status = (
        "Available"
        if available is True
        else "Unavailable"
        if available is False
        else calibration.get("status")
    )
    return (
        ("Status", status),
        ("Sample size", calibration.get("sample_size") or calibration.get("trades")),
        ("Expected R", calibration.get("expected_r")),
        ("Win rate", calibration.get("win_rate")),
        ("Reason", calibration.get("reason")),
    )


def _scan_explain_opportunities(
    payload: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    opportunities: list[Mapping[str, object]] = []
    for result in _mappings(payload.get("results")):
        portfolio = _mapping(result.get("opportunity_portfolio"))
        opportunities.extend(_mappings(portfolio.get("opportunities")))
    return tuple(opportunities)


def _scan_explain_sections(payload: Mapping[str, object]) -> list[str]:
    """Aggregate per-symbol diagnostics for scan explain mode.

    Scan diagnostics live on each serialized symbol result. Treating the scan payload
    as one selected-symbol payload produces empty methodology counts and hides the
    reasons every candidate was rejected. This adapter keeps scan and analyze on the
    same canonical evidence while presenting a scan-wide diagnostic summary.
    """

    results = _mappings(payload.get("results"))
    sections: list[str] = []

    methodology = _scan_methodology_enforcement_fields(payload, results)
    sections.append(render_section("Methodology enforcement", render_fields(methodology)))

    portfolio_lines = _scan_prefixed_portfolio_lines(results)
    sections.append(
        render_section(
            "Opportunity portfolio",
            render_bullets(portfolio_lines or ("No opportunities were retained.",)),
        )
    )

    timeframe = _scan_prefixed_result_lines(results, multi_timeframe_lines)
    sections.append(
        render_section(
            "Multi-timeframe evidence",
            render_bullets(timeframe or ("No multi-timeframe evidence was serialized.",)),
        )
    )

    entry, stop, target = _scan_rationale_groups(results)
    sections.append(
        render_section(
            "Entry and chase rationale",
            render_bullets(entry or ("No retained entry or chase geometry is available.",)),
        )
    )
    sections.append(
        render_section(
            "Stop rationale",
            render_bullets(stop or ("No retained stop geometry is available.",)),
        )
    )
    sections.append(
        render_section(
            "Target rationale",
            render_bullets(target or ("No retained target geometry is available.",)),
        )
    )

    evidence = _scan_prefixed_opportunity_lines(results, _canonical_evidence_lines)
    sections.append(
        render_section(
            "Supporting evidence",
            render_bullets(evidence or ("No retained opportunity evidence is available.",)),
        )
    )

    contradictions = _scan_prefixed_opportunity_lines(
        results,
        _canonical_contradiction_lines,
    )
    sections.append(
        render_section(
            "Contradictions",
            render_bullets(
                contradictions or ("No retained-opportunity contradictions were serialized.",)
            ),
        )
    )

    missing = _scan_missing_evidence_summary(results)
    sections.append(
        render_section(
            "Missing evidence",
            render_bullets(missing or ("No explicit missing-evidence record was serialized.",)),
        )
    )

    collisions = _scan_prefixed_result_lines(results, diagnostic_summary_lines)
    sections.append(
        render_section(
            "Collision and sequence",
            render_bullets(
                collisions or ("No collision or sequence diagnostics were serialized.",)
            ),
        )
    )

    rejected, rejected_total = _scan_rejected_lines(results)
    sections.append(
        render_section(
            "Rejected and suppressed candidates",
            render_bullets(rejected or ("No rejected-candidate details were serialized.",)),
        )
    )
    if rejected_total > len(rejected):
        sections.append(
            render_section(
                "Explain display limits",
                render_bullets(
                    (
                        f"Showing {len(rejected)} of {rejected_total} rejected candidates.",
                        "Use --output json for the complete structured record.",
                    )
                ),
            )
        )

    data_lines = _scan_data_quality_lines(payload, results)
    sections.append(
        render_section(
            "Data quality",
            render_bullets(data_lines or ("No data-quality warnings were reported.",)),
        )
    )

    tracking = _outcome_tracking_fields(payload)
    sections.append(
        render_section(
            "Outcome-tracking status",
            render_fields(
                tracking
                or (
                    ("Outcome tracking", "Unavailable"),
                    ("Database", "No outcome-tracking status was serialized"),
                )
            ),
        )
    )

    calibration = _historical_calibration_fields(payload)
    sections.append(
        render_section(
            "Historical calibration",
            render_fields(
                calibration
                or (
                    ("Status", "Unavailable"),
                    ("Reason", "No historical calibration sample is attached to this scan"),
                )
            ),
        )
    )
    return sections


def _scan_missing_evidence_summary(
    results: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    """Aggregate repeated scan-wide gaps instead of printing one line per symbol."""

    symbols_by_gap: dict[str, list[str]] = {}
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        for line in _missing_evidence_lines(result):
            gap = line.removeprefix("Unavailable: ")
            symbols_by_gap.setdefault(gap, []).append(symbol)

    lines: list[str] = []
    for gap, symbols in symbols_by_gap.items():
        unique = tuple(dict.fromkeys(symbols))
        preview = ", ".join(unique[:3])
        remainder = len(unique) - min(3, len(unique))
        suffix = f", +{remainder} more" if remainder else ""
        lines.append(f"{gap}: unavailable for {len(unique)} symbol(s) ({preview}{suffix})")
    return tuple(lines)


def _scan_methodology_enforcement_fields(
    payload: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, object], ...]:
    totals = {
        "evaluated": 0,
        "allowed": 0,
        "deferred": 0,
        "suppressed": 0,
        "unavailable": 0,
    }
    for result in results:
        portfolio = _mapping(result.get("opportunity_portfolio"))
        opportunities = _mappings(portfolio.get("opportunities"))
        fields = dict(_methodology_enforcement_fields(result, opportunities))
        for field, key in (
            ("Candidates evaluated", "evaluated"),
            ("Allowed", "allowed"),
            ("Deferred", "deferred"),
            ("Suppressed", "suppressed"),
            ("Unavailable", "unavailable"),
        ):
            value = _number(fields.get(field))
            if value is not None:
                totals[key] += int(value)

    gate_mode = (
        payload.get("methodology_gate_mode")
        or _mapping(payload.get("configuration")).get("methodology_gate_mode")
        or _scan_methodology_status(payload)
    )
    return (
        ("Gate mode", humanize_code(gate_mode)),
        ("Candidates evaluated", totals["evaluated"]),
        ("Allowed", totals["allowed"]),
        ("Deferred", totals["deferred"]),
        ("Suppressed", totals["suppressed"]),
        ("Unavailable", totals["unavailable"]),
    )


def _scan_prefixed_portfolio_lines(
    results: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        portfolio = _mapping(result.get("opportunity_portfolio"))
        for line in _canonical_portfolio_lines(_mappings(portfolio.get("opportunities"))):
            lines.append(f"{symbol} — {line}")
    return tuple(dict.fromkeys(lines))


def _scan_prefixed_result_lines(
    results: Sequence[Mapping[str, object]],
    factory: Callable[[Mapping[str, object]], Sequence[str]],
) -> tuple[str, ...]:
    lines: list[str] = []
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        produced = factory(result)
        lines.extend(f"{symbol} — {line}" for line in produced)
    return tuple(dict.fromkeys(lines))


def _scan_prefixed_opportunity_lines(
    results: Sequence[Mapping[str, object]],
    factory: Callable[
        [Mapping[str, object], Sequence[Mapping[str, object]]],
        Sequence[str],
    ],
) -> tuple[str, ...]:
    lines: list[str] = []
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        portfolio = _mapping(result.get("opportunity_portfolio"))
        opportunities = _mappings(portfolio.get("opportunities"))
        produced = factory(result, opportunities)
        lines.extend(f"{symbol} — {line}" for line in produced)
    return tuple(dict.fromkeys(lines))


def _scan_rationale_groups(
    results: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
    entry: list[str] = []
    stop: list[str] = []
    target: list[str] = []
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        portfolio = _mapping(result.get("opportunity_portfolio"))
        opportunities = _mappings(portfolio.get("opportunities"))
        for opportunity in opportunities:
            setup = _mapping(opportunity.get("setup")) or opportunity
            identity = opportunity.get("opportunity_id") or "Opportunity"
            for line in rationale_lines(result, setup):
                rendered = f"{symbol} • {identity} — {line}"
                normalized = line.lower()
                if any(token in normalized for token in ("stop", "invalid")):
                    stop.append(rendered)
                elif any(token in normalized for token in ("target", "tp", "reward", "room")):
                    target.append(rendered)
                else:
                    entry.append(rendered)
    return (
        tuple(dict.fromkeys(entry)),
        tuple(dict.fromkeys(stop)),
        tuple(dict.fromkeys(target)),
    )


def _scan_rejected_lines(
    results: Sequence[Mapping[str, object]],
) -> tuple[tuple[str, ...], int]:
    lines: list[str] = []
    total = 0
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        produced = tuple(
            dict.fromkeys(
                (
                    *rejected_candidate_lines(result),
                    *_methodology_suppressed_candidate_lines(result),
                )
            )
        )
        total += max(_rejected_candidate_count(result), len(produced))
        lines.extend(f"{symbol} — {line}" for line in produced)
    return tuple(dict.fromkeys(lines)), total


def _scan_data_quality_lines(
    payload: Mapping[str, object],
    results: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    lines = list(_scan_failure_lines(payload))
    for result in results:
        symbol = str(result.get("symbol") or "Unknown market")
        lines.extend(f"{symbol} — {line}" for line in _data_diagnostic_lines(result))
    return tuple(dict.fromkeys(lines))


def _no_trade_sections(
    payload: Mapping[str, object],
    focused: Mapping[str, object],
    *,
    explain: bool,
) -> list[str]:
    assessment = _mapping(focused.get("directional_assessment"))
    reasons = _clean_many(payload.get("reasons"))
    reason = reasons[0] if reasons else "No defensible entry with defined risk is available."
    sections = [
        render_section(
            "Decision",
            "\n".join(
                (
                    "▶  NO TRADE RIGHT NOW",
                    render_fields(
                        (
                            ("Directional bias", humanize_code(assessment.get("preferred_side"))),
                            ("Reason", reason),
                        )
                    ),
                )
            ),
        )
    ]
    watch = _watch_items(focused)
    if watch:
        sections.append(render_section("Next valid setup", render_bullets(watch[:4])))
    context = _market_context(focused)
    if context:
        sections.append(context)
    if explain:
        signal = _signal_snapshot(payload)
        if signal:
            sections.append(signal)
        sections.extend(_side_explanation(focused))
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
    actionability = canonical_actionability_state(setup).lower()

    if actionability in {"execute_now", "aggressive_now"} and not pending:
        action = f"ENTER {direction.upper()}"
    elif actionability == "execute_on_micro_confirmation" and not pending:
        action = "WAIT FOR MICRO CONFIRMATION"
    elif actionability in {"invalidated", "missed_or_chasing"}:
        action = "SKIP — INVALID OR CHASED"
    else:
        action = "VALID SETUP — WAIT FOR ENTRY"

    quality = _mapping(setup.get("quality_dimensions"))
    sections = [
        render_section(
            "Decision",
            "\n".join(
                (
                    f"▶  {action}",
                    render_fields(
                        (
                            ("Side", direction),
                            ("Strategy", humanize_code(setup.get("strategy"))),
                            ("Actionability", _actionability_label(setup)),
                            (
                                "Trade quality",
                                _quality(
                                    quality.get("overall_trade_quality")
                                    or quality.get("setup_quality")
                                    or setup.get("confidence_score")
                                ),
                            ),
                        )
                    ),
                )
            ),
        )
    ]

    preferred = _number(entry.get("preferred"))
    current = _number(entry.get("current_price"))
    plan: list[tuple[str, object]] = [
        ("Current price", format_price(entry.get("current_price"))),
        _entry_field(entry),
        ("Preferred entry", format_price(entry.get("preferred"))),
        ("Stop", _price_with_move(stop.get("price"), preferred or current)),
    ]
    chase_label = (
        "Do not chase below" if setup.get("direction") == "short" else "Do not chase above"
    )
    plan.append((chase_label, format_price(entry.get("maximum_chase_price"))))
    for index, target in enumerate(targets[:3], start=1):
        plan.append(
            (
                f"TP{index}",
                _target_label(target, reference=preferred or current),
            )
        )
    sections.append(render_section("Trade plan", render_fields(plan)))

    timeframe_map = multi_timeframe_lines(payload)
    if timeframe_map:
        sections.append(render_section("Multi-timeframe view", render_bullets(timeframe_map)))

    if pending:
        conditional = _conditional_plan_section(setup)
        if conditional:
            sections.append(conditional)
        sections.append(
            render_section("Activation needed", render_bullets(_activation(setup, focused)[:4]))
        )

    reasons = _clean_many(payload.get("reasons"))
    if reasons:
        sections.append(render_section("Why this trade", render_bullets(reasons[:3])))

    warnings = list(_clean_many(setup.get("warnings")))
    feasibility = _mapping(payload.get("methodology_target_feasibility_semantics"))
    if feasibility.get("costs_available") is False:
        warnings.append("fees and slippage are not included in target feasibility")
    if warnings:
        sections.append(render_section("Main risks", render_bullets(warnings[:3])))

    alternatives = _mappings(setup.get("alternative_entry_opportunities"))
    if alternatives:
        lines = [
            f"{_price_range(item.get('lower'), item.get('upper'))} • preferred "
            f"{format_price(item.get('preferred'))}"
            for item in alternatives[:2]
        ]
        sections.append(render_section("Alternative entry", render_bullets(lines)))

    if explain:
        signal = _signal_snapshot(payload)
        if signal:
            sections.append(signal)
        opportunity_map = opportunity_map_lines(payload)
        if opportunity_map:
            sections.append(render_section("Opportunity map", render_bullets(opportunity_map)))
        rationale = rationale_lines(payload, setup)
        if rationale:
            sections.append(render_section("Geometry rationale", render_bullets(rationale)))
        evidence = evidence_contradiction_lines(payload, setup)
        if evidence:
            sections.append(render_section("Evidence and contradictions", render_bullets(evidence)))
        diagnostics = diagnostic_summary_lines(payload)
        if diagnostics:
            sections.append(render_section("Lifecycle and collision", render_bullets(diagnostics)))
        rejected = rejected_candidate_lines(payload)
        if rejected:
            sections.append(render_section("Rejected candidates", render_bullets(rejected)))
        sections.extend(_setup_explanation(setup, focused))
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
                f"▶  #{index}  {symbol} • NO TRADE",
                render_fields((("Reason", reasons[0] if reasons else "No valid setup formed"),)),
            )
        )

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    targets = _mappings(setup.get("take_profits"))
    quality = _mapping(setup.get("quality_dimensions"))
    reference = _number(entry.get("preferred")) or _number(entry.get("current_price"))
    fields: list[tuple[str, object]] = [
        ("Action", _actionability_label(setup)),
        ("Side", humanize_code(setup.get("direction"))),
        ("Strategy", humanize_code(setup.get("strategy"))),
        ("CMP", format_price(entry.get("current_price"))),
        ("Entry", _price_range(entry.get("lower"), entry.get("upper"))),
        ("Preferred", format_price(entry.get("preferred"))),
        ("Stop", _price_with_move(stop.get("price"), reference)),
    ]
    for target_index, target in enumerate(targets[:3], start=1):
        fields.append((f"TP{target_index}", _target_label(target, reference=reference)))
    fields.extend(
        (
            (
                "Trade quality",
                _quality(
                    quality.get("overall_trade_quality")
                    or quality.get("setup_quality")
                    or setup.get("confidence_score")
                ),
            ),
            ("Execution quality", _quality(quality.get("execution_quality"))),
        )
    )
    warning = data_quality_warning(payload)
    if warning:
        fields.append(("Data warning", warning))
    warnings = _clean_many(setup.get("warnings"))
    if warnings:
        fields.append(("Main risk", warnings[0]))
    if developing and not selected:
        fields.append(("Wait for", _activation(setup, {})[0]))
        fields.extend(_conditional_scan_fields(setup))
    return "\n".join((f"▶  #{index}  {symbol}", render_fields(fields)))


def _conditional_plan_section(setup: Mapping[str, object]) -> str:
    plan = _mapping(setup.get("conditional_plan"))
    if not plan:
        return ""
    trigger = _mapping(plan.get("trigger"))
    invalidation = _mapping(plan.get("pre_entry_invalidation"))
    expiry = _mapping(plan.get("expiry"))
    return render_section(
        "Conditional entry plan",
        render_fields(
            (
                ("Trigger", humanize_code(trigger.get("type"))),
                ("Trigger level", format_price(trigger.get("level"))),
                ("Condition", trigger.get("condition")),
                (
                    "Confirmation timeframe",
                    trigger.get("confirmation_timeframe") or UNAVAILABLE,
                ),
                ("Pre-entry invalidation", format_price(invalidation.get("price"))),
                ("Cancel when", invalidation.get("condition")),
                ("Order intent", humanize_code(plan.get("recommended_order_intent"))),
                (
                    "Resting order authorized",
                    ("Yes" if plan.get("conditional_order_eligible") is True else "No"),
                ),
                ("Valid for", expiry.get("validity") or UNAVAILABLE),
                ("Expiry reason", expiry.get("reason") or UNAVAILABLE),
            )
        ),
    )


def _conditional_scan_fields(
    setup: Mapping[str, object],
) -> tuple[tuple[str, object], ...]:
    plan = _mapping(setup.get("conditional_plan"))
    if not plan:
        return ()
    trigger = _mapping(plan.get("trigger"))
    invalidation = _mapping(plan.get("pre_entry_invalidation"))
    return (
        (
            "Trigger",
            f"{humanize_code(trigger.get('type'))} at {format_price(trigger.get('level'))}",
        ),
        ("Pre-entry invalidation", format_price(invalidation.get("price"))),
        ("Order intent", humanize_code(plan.get("recommended_order_intent"))),
    )


def _market_context(focused: Mapping[str, object]) -> str:
    outlook = _mapping(focused.get("market_outlook"))
    if not outlook:
        return ""
    return render_section(
        "Market context",
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
        fields.extend(
            (
                ("Early warning", humanize_code(warning.get("state"))),
                ("Directional lean", humanize_code(warning.get("direction"))),
                ("Main evidence", evidence[0] if evidence else UNAVAILABLE),
                ("Main concern", concerns[0] if concerns else UNAVAILABLE),
            )
        )
    if edge and edge.get("available") is True:
        expected_r = edge.get("expected_r")
        fields.extend(
            (
                ("Historical edge", "Validated"),
                (
                    "Expected return",
                    f"{float(expected_r):+.2f}R"
                    if isinstance(expected_r, int | float)
                    else UNAVAILABLE,
                ),
            )
        )
    return render_section("Signal evidence", render_fields(fields)) if fields else ""


def _side_explanation(focused: Mapping[str, object]) -> list[str]:
    sections: list[str] = []
    for label, key in (("Long assessment", "long_thesis"), ("Short assessment", "short_thesis")):
        thesis = _mapping(focused.get(key))
        if not thesis:
            continue
        blockers = _clean_many(thesis.get("blockers"))
        body = render_fields(
            (
                ("State", humanize_code(thesis.get("state"))),
                ("Best strategy", humanize_code(thesis.get("primary_strategy"))),
                ("Quality", _quality(thesis.get("score"))),
                ("Summary", _clean(thesis.get("summary"))),
            )
        )
        if blockers:
            body += "\n\n" + render_bullets(blockers[:4])
        sections.append(render_section(label, body))
    return sections


def _setup_explanation(
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


def _weak_invalid_lines(items: Sequence[Mapping[str, object]]) -> tuple[str, ...]:
    lines: list[str] = []
    for payload in items[:8]:
        symbol = str(payload.get("symbol") or "Unknown market")
        reasons = _clean_many(payload.get("reasons"))
        lines.append(f"{symbol} — {reasons[0] if reasons else 'No valid setup formed'}")
    hidden = max(0, len(items) - len(lines))
    if hidden:
        lines.append(f"{hidden} additional markets not expanded")
    return tuple(lines)


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
    return useful or _watch_items(focused) or ("Wait for the stated entry conditions.",)


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


def _target_label(
    target: Mapping[str, object],
    *,
    reference: float | None,
    target_quality: object = None,
) -> str:
    price = target.get("price")
    gross_rr = format_ratio(target.get("gross_risk_reward") or target.get("risk_reward"))
    net_rr = format_ratio(target.get("net_risk_reward"))
    move = _move_pct(price, reference)
    suffixes: list[str] = []
    if move is not None:
        suffixes.append(f"{move:+.2f}%")
    if gross_rr != UNAVAILABLE:
        suffixes.append(f"{gross_rr}R gross")
    if net_rr != UNAVAILABLE:
        suffixes.append(f"{net_rr}R net")

    quality = _quality(target_quality)
    if target_quality is not None and quality != UNAVAILABLE:
        suffixes.append(f"target quality {quality}")

    purpose = target.get("purpose")
    if _available_output_value(purpose):
        suffixes.append(_clean(purpose))

    suffix = " • " + " • ".join(suffixes) if suffixes else ""
    return f"{format_price(price)}{suffix}"


def _price_with_move(price: object, reference: float | None) -> str:
    move = _move_pct(price, reference)
    return format_price(price) if move is None else f"{format_price(price)} • {move:+.2f}%"


def _move_pct(price: object, reference: float | None) -> float | None:
    numeric = _number(price)
    if numeric is None or reference is None or reference == 0:
        return None
    return (numeric - reference) / reference * 100.0


def _number(value: object) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    return None


def _clean(value: object) -> str:
    if value is None:
        return UNAVAILABLE
    text = str(value).strip()
    replacements = (
        (
            r"all candidates scored below their configured approval thresholds",
            "No setup reached the required trade quality.",
        ),
        (
            r"all candidates were rejected by deterministic candidate-selection rules",
            "No setup passed the current structure and execution checks.",
        ),
        (
            r"active-candle evidence is provisional",
            "Current-candle confirmation remains incomplete.",
        ),
        (
            r"rule-based quality is below the configured approval threshold",
            "Setup quality is below the required level.",
        ),
        (
            r"score [\d.]+ is below aggressive floor [\d.]+",
            "Setup quality is below the aggressive-entry requirement.",
        ),
        (
            r"no (long|short) candidate passed strategy generation",
            r"No clear \1 setup formed.",
        ),
    )
    for pattern, replacement in replacements:
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    text = re.sub(r";?\s*cross-sectional raw score\s+[-+\d.]+", "", text, flags=re.IGNORECASE)
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


__all__ = ["render_analysis", "render_scan"]
