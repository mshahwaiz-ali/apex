"""Trader-facing futures analysis presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_amount,
    format_percentage,
    format_price,
    format_ratio,
    format_score,
    humanize_code,
    humanize_warnings,
    normalize_output_mode,
    render_bullets,
    render_fields,
    render_section,
    render_title,
)


def render_futures_analysis(
    payload: Mapping[str, object],
    *,
    mode: str | OutputMode = OutputMode.TEXT,
) -> str:
    """Render one serialized futures analysis without recomputing trading logic."""

    output_mode = normalize_output_mode(mode)
    symbol = str(payload.get("symbol") or "Unknown symbol")
    setup = _mapping(_mapping(payload.get("assessment")).get("setup"))
    decision = "No Trade" if not setup else humanize_code(setup.get("direction")) + " Setup"

    sections = [render_title(f"{symbol} — {decision}")]
    sections.append(_render_market_view(payload))
    sections.append(_render_trade_decision(payload, setup))

    if setup:
        sections.append(_render_action(setup, payload))
        sections.append(_render_trade_quality(setup, payload))
    else:
        sections.append(_render_watch_conditions(payload))

    risk_profile = _render_risk_profile(payload)
    if risk_profile:
        sections.append(risk_profile)

    warnings = _warnings(payload)
    if warnings:
        sections.append(render_section("Warnings", render_bullets(warnings)))

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        diagnostics = _render_diagnostics(payload, debug=output_mode is OutputMode.DEBUG)
        if diagnostics:
            sections.append(diagnostics)

    return "\n\n".join(section for section in sections if section)


def _render_market_view(payload: Mapping[str, object]) -> str:
    environment = _mapping(payload.get("market_environment"))
    route = _mapping(payload.get("market_strategy_route"))
    regime = environment.get("primary_regime") or environment.get("regime")
    higher_bias = environment.get("higher_timeframe_bias") or environment.get("htf_bias")
    preferred = route.get("preferred_direction")
    volatility = environment.get("volatility_regime") or environment.get("volatility")
    extension = environment.get("extension_state") or environment.get("extension")

    return render_section(
        "Market View",
        render_fields(
            (
                ("Bias", humanize_code(higher_bias)),
                ("Preferred side", humanize_code(preferred)),
                ("Market condition", humanize_code(regime)),
                ("Current volatility", humanize_code(volatility)),
                ("Market extended", _yes_no(extension)),
            )
        ),
    )


def _render_trade_decision(
    payload: Mapping[str, object], setup: Mapping[str, object]
) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    route = _mapping(payload.get("market_strategy_route"))
    decision_code = payload.get("decision_reason_code")
    action = humanize_code(near_entry.get("entry_state")) if near_entry else "No trade right now"
    if setup and action == "Unavailable":
        action = "Trade setup available"

    long_score, short_score = _direction_scores(payload)
    reason = _decision_reason(payload, setup)

    return render_section(
        "Trade Decision",
        render_fields(
            (
                ("Action", action),
                ("Long opportunity", _opportunity_label(long_score, "long", route)),
                ("Short opportunity", _opportunity_label(short_score, "short", route)),
                ("Reason", reason or humanize_code(decision_code)),
            )
        ),
    )


def _render_watch_conditions(payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    reasons = _string_sequence(near_entry.get("reasons"))
    route = _mapping(payload.get("market_strategy_route"))
    preferred = humanize_code(route.get("preferred_direction"))
    trigger = near_entry.get("nearest_future_trigger") or near_entry.get("trigger_price")

    items: list[tuple[str, object]] = []
    if reasons:
        items.append(("Current condition", reasons[0]))
    if preferred != "Unavailable":
        items.append(("Preferred side", preferred))
    if trigger is not None:
        items.append(("Nearest trigger", format_price(trigger)))
    if not items:
        items.append(("Next step", "Wait for a valid setup to form near the current price"))

    return render_section("What Would Change the Decision", render_fields(items))


def _render_action(setup: Mapping[str, object], payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    entry_zone = _mapping(setup.get("entry_zone") or setup.get("entry"))
    take_profits = _mapping_sequence(setup.get("take_profits"))
    fields: list[tuple[str, object]] = [
        ("Status", humanize_code(near_entry.get("entry_state"))),
        ("Direction", humanize_code(setup.get("direction"))),
        ("Strategy", humanize_code(setup.get("strategy"))),
        ("Current price", format_price(setup.get("current_price") or entry_zone.get("current_price"))),
        ("Entry zone", _price_range(entry_zone.get("low") or entry_zone.get("lower"), entry_zone.get("high") or entry_zone.get("upper"))),
        ("Ideal entry", format_price(entry_zone.get("preferred") or entry_zone.get("ideal_entry"))),
        ("Maximum chase price", format_price(entry_zone.get("max_chase_price") or entry_zone.get("maximum_chase_price"))),
        ("Stop loss", format_price(setup.get("stop_loss") or _mapping(setup.get("invalidation")).get("price"))),
    ]
    for index, target in enumerate(take_profits[:3], start=1):
        fields.append((f"Take profit {index}", format_price(target.get("price"))))
    if take_profits:
        fields.append(("Risk/reward", format_ratio(take_profits[0].get("risk_reward"))))
    return render_section("Action", render_fields(fields))


def _render_trade_quality(setup: Mapping[str, object], payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    return render_section(
        "Trade Quality",
        render_fields(
            (
                ("Setup confidence", format_score(setup.get("confidence_score"))),
                ("Entry quality", format_score(near_entry.get("entry_quality_score"))),
                ("Chase risk", humanize_code(near_entry.get("chase_risk"))),
                ("Actionable now", _yes_no(near_entry.get("actionable_now"))),
            )
        ),
    )


def _render_risk_profile(payload: Mapping[str, object]) -> str:
    account = _mapping(payload.get("futures_account"))
    plan = _mapping(payload.get("futures_plan"))
    if not account and not plan:
        return ""

    fields: list[tuple[str, object]] = [
        ("Wallet", format_amount(account.get("wallet_balance"), currency="USDT")),
        ("Risk mode", humanize_code(account.get("risk_mode"))),
        ("Maximum planned loss", format_amount(account.get("maximum_account_loss_amount"), currency="USDT")),
        ("Margin mode", humanize_code(account.get("margin_mode"))),
        ("Leverage mode", humanize_code(account.get("leverage_mode"))),
    ]
    approved = _mapping(plan.get("plan")) or plan
    optional_fields = (
        ("Leverage", approved.get("leverage")),
        ("Position size", approved.get("quantity") or approved.get("position_size")),
        ("Required margin", approved.get("required_margin")),
        ("Estimated liquidation", approved.get("estimated_liquidation_price")),
        ("Liquidation buffer", approved.get("liquidation_buffer_percentage")),
    )
    for label, value in optional_fields:
        if value is None:
            continue
        if label in {"Required margin"}:
            rendered = format_amount(value, currency="USDT")
        elif label in {"Estimated liquidation"}:
            rendered = format_price(value)
        elif label in {"Liquidation buffer"}:
            rendered = format_percentage(value)
        else:
            rendered = str(value)
        fields.append((label, rendered))
    return render_section("Risk Profile", render_fields(fields))


def _render_diagnostics(payload: Mapping[str, object], *, debug: bool) -> str:
    fields: list[tuple[str, object]] = [
        ("Decision reason", humanize_code(payload.get("decision_reason_code"))),
        ("Candidates evaluated", payload.get("candidate_count")),
    ]
    route = _mapping(payload.get("market_strategy_route"))
    if route:
        fields.append(("Routing score", format_score(route.get("routing_score"))))
        priorities = _string_sequence(route.get("strategy_priority"))
        fields.append(("Strategies considered", ", ".join(humanize_code(item) for item in priorities) or "Unavailable"))
    if debug:
        fields.append(("Raw decision code", payload.get("decision_reason_code")))
        fields.append(("Phase diagnostics present", _yes_no(bool(payload.get("phase5_diagnostics")))))
    return render_section("Diagnostics", render_fields(fields))


def _decision_reason(payload: Mapping[str, object], setup: Mapping[str, object]) -> str:
    if setup:
        near_entry = _mapping(payload.get("near_current_entry"))
        reasons = _string_sequence(near_entry.get("reasons"))
        return reasons[0] if reasons else "Approved setup satisfies the current trade criteria"
    code = str(payload.get("decision_reason_code") or "")
    explanations = {
        "NO_CANDIDATE_GENERATED": "No valid setup formed near the current price",
        "CANDIDATE_REJECTED": "A setup formed but did not meet the required quality or risk standards",
        "NO_ROUTED_STRATEGY": "No strategy matched the current market condition",
        "ENVIRONMENT_BLOCKED": "Current market conditions are not safe enough to trade",
        "MISSED_ENTRY": "The valid entry has already passed",
        "INVALIDATED": "The setup was invalidated before entry",
        "WAIT_FOR_RECLAIM": "Price must reclaim the required structure before entry",
        "WAIT_FOR_RETEST": "Price must retest the required level before entry",
    }
    return explanations.get(code, humanize_code(code))


def _direction_scores(payload: Mapping[str, object]) -> tuple[float | None, float | None]:
    environment = _mapping(payload.get("market_environment"))
    return _number(environment.get("long_suitability")), _number(environment.get("short_suitability"))


def _opportunity_label(
    score: float | None,
    direction: str,
    route: Mapping[str, object],
) -> str:
    preferred = str(route.get("preferred_direction") or "").lower()
    if score is None:
        return "Preferred" if preferred == direction else "Not preferred"
    if score >= 75:
        strength = "Strong"
    elif score >= 55:
        strength = "Moderate"
    elif score >= 35:
        strength = "Weak"
    else:
        strength = "Very weak"
    return f"{strength} ({format_score(score)})"


def _warnings(payload: Mapping[str, object]) -> tuple[str, ...]:
    environment = _mapping(payload.get("market_environment"))
    warnings = payload.get("warnings") or environment.get("warnings") or ()
    return humanize_warnings(_string_sequence(warnings))


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mapping_sequence(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


def _string_sequence(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item) for item in value)


def _number(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    return float(value)


def _price_range(low: object, high: object) -> str:
    if low is None and high is None:
        return "Unavailable"
    if low is None:
        return format_price(high)
    if high is None:
        return format_price(low)
    return f"{format_price(low)} – {format_price(high)}"


def _yes_no(value: object) -> str:
    if value is None:
        return "Unavailable"
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized in {"NONE", "NORMAL", "NOT_EXTENDED", "FALSE", "NO"}:
            return "No"
        if normalized in {"EXTENDED", "EXTREME", "TRUE", "YES"}:
            return "Yes"
        return humanize_code(value)
    return "Yes" if bool(value) else "No"


__all__ = ["render_futures_analysis"]
