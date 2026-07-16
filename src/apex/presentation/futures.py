"""Trader-facing futures analysis presentation."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.presentation import (
    OutputMode,
    format_amount,
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
    approved = str(payload.get("decision") or "NO_TRADE").upper() != "NO_TRADE"
    decision = f"{humanize_code(payload.get('decision'))} Setup" if approved else "No Trade"

    sections = [render_title(f"{symbol} — {decision}")]
    sections.append(_render_market_view(payload))
    sections.append(_render_trade_decision(payload, approved=approved))
    if approved:
        sections.append(_render_action(payload))
        sections.append(_render_trade_quality(payload))
    else:
        sections.append(_render_watch_conditions(payload))

    risk_profile = _render_risk_profile(payload)
    if risk_profile:
        sections.append(risk_profile)

    warnings = _warnings(payload)
    if warnings:
        sections.append(render_section("Warnings", render_bullets(warnings)))

    if output_mode in {OutputMode.VERBOSE, OutputMode.DEBUG}:
        sections.append(_render_diagnostics(payload, debug=output_mode is OutputMode.DEBUG))

    return "\n\n".join(section for section in sections if section)


def _render_market_view(payload: Mapping[str, object]) -> str:
    environment = _mapping(payload.get("market_environment"))
    route = _mapping(payload.get("market_strategy_route"))
    return render_section(
        "Market View",
        render_fields(
            (
                ("Bias", humanize_code(environment.get("higher_timeframe_bias"))),
                ("Preferred side", humanize_code(route.get("preferred_direction"))),
                ("Market condition", humanize_code(environment.get("primary_regime"))),
                ("Current volatility", humanize_code(environment.get("volatility_state"))),
                ("Market extended", _yes_no(environment.get("extension_state"))),
            )
        ),
    )


def _render_trade_decision(payload: Mapping[str, object], *, approved: bool) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    route = _mapping(payload.get("market_strategy_route"))
    action = humanize_code(near_entry.get("entry_state") or payload.get("entry_state"))
    if action == "Unavailable":
        action = "Trade setup available" if approved else "No trade right now"
    long_score, short_score = _direction_scores(payload)
    return render_section(
        "Trade Decision",
        render_fields(
            (
                ("Action", action),
                ("Long opportunity", _opportunity_label(long_score, "long", route)),
                ("Short opportunity", _opportunity_label(short_score, "short", route)),
                ("Reason", _decision_reason(payload, approved=approved)),
            )
        ),
    )


def _render_watch_conditions(payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    route = _mapping(payload.get("market_strategy_route"))
    reasons = _strings(near_entry.get("reasons")) or _strings(payload.get("reasons"))
    fields: list[tuple[str, object]] = []
    if reasons:
        fields.append(("Current condition", reasons[0]))
    preferred = humanize_code(route.get("preferred_direction"))
    if preferred != "Unavailable":
        fields.append(("Preferred side", preferred))
    trigger = near_entry.get("nearest_future_trigger") or near_entry.get("trigger_price")
    if trigger is not None:
        fields.append(("Nearest trigger", format_price(trigger)))
    if not fields:
        fields.append(("Next step", "Wait for a valid setup to form near the current price"))
    return render_section("What Would Change the Decision", render_fields(fields))


def _render_action(payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    entry_zone = _mapping(payload.get("entry_zone"))
    targets = _mappings(payload.get("take_profits"))
    fields: list[tuple[str, object]] = [
        ("Status", humanize_code(near_entry.get("entry_state") or payload.get("entry_state"))),
        ("Direction", humanize_code(payload.get("decision"))),
        ("Strategy", humanize_code(payload.get("strategy"))),
        ("Current price", format_price(payload.get("current_price"))),
        ("Entry zone", _price_range(entry_zone.get("low"), entry_zone.get("high"))),
        ("Ideal entry", format_price(entry_zone.get("preferred"))),
        ("Maximum chase price", format_price(entry_zone.get("maximum_chase_price"))),
        ("Stop loss", format_price(payload.get("stop_loss"))),
    ]
    for index, target in enumerate(targets[:3], start=1):
        fields.append((f"Take profit {index}", format_price(target.get("price"))))
    if targets:
        fields.append(("Risk/reward", format_ratio(targets[0].get("risk_reward"))))
    return render_section("Action", render_fields(fields))


def _render_trade_quality(payload: Mapping[str, object]) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    return render_section(
        "Trade Quality",
        render_fields(
            (
                ("Setup confidence", format_score(payload.get("confidence_score"))),
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
    plan_data = _mapping(plan.get("plan")) or plan
    for label, key in (
        ("Leverage", "leverage"),
        ("Position size", "quantity"),
        ("Required margin", "required_margin"),
        ("Estimated liquidation", "estimated_liquidation_price"),
    ):
        value = plan_data.get(key)
        if value is not None:
            fields.append((label, format_price(value) if "liquidation" in key else str(value)))
    return render_section("Risk Profile", render_fields(fields))


def _render_diagnostics(payload: Mapping[str, object], *, debug: bool) -> str:
    route = _mapping(payload.get("market_strategy_route"))
    fields: list[tuple[str, object]] = [
        ("Decision reason", humanize_code(payload.get("decision_reason_code"))),
        ("Candidates evaluated", payload.get("candidate_count")),
        ("Routing score", format_score(route.get("routing_score"))),
    ]
    priorities = _strings(route.get("strategy_priority"))
    if priorities:
        fields.append(("Strategies considered", ", ".join(humanize_code(item) for item in priorities)))
    if debug:
        fields.extend(
            (
                ("Raw decision code", payload.get("decision_reason_code")),
                ("Phase diagnostics present", _yes_no(bool(payload.get("phase5_diagnostics")))),
            )
        )
    return render_section("Diagnostics", render_fields(fields))


def _decision_reason(payload: Mapping[str, object], *, approved: bool) -> str:
    near_entry = _mapping(payload.get("near_current_entry"))
    reasons = _strings(near_entry.get("reasons"))
    if approved:
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
    if code in explanations:
        return explanations[code]
    fallback = _strings(payload.get("reasons"))
    return fallback[0] if fallback else humanize_code(code)


def _direction_scores(payload: Mapping[str, object]) -> tuple[float | None, float | None]:
    environment = _mapping(payload.get("market_environment"))
    return (
        _number(environment.get("long_suitability_score")),
        _number(environment.get("short_suitability_score")),
    )


def _opportunity_label(score: float | None, direction: str, route: Mapping[str, object]) -> str:
    if score is None:
        preferred = str(route.get("preferred_direction") or "").lower()
        return "Preferred" if preferred == direction else "Not preferred"
    strength = "Strong" if score >= 75 else "Moderate" if score >= 55 else "Weak" if score >= 35 else "Very weak"
    return f"{strength} ({format_score(score)})"


def _warnings(payload: Mapping[str, object]) -> tuple[str, ...]:
    environment = _mapping(payload.get("market_environment"))
    values = payload.get("warnings") or environment.get("reason_codes") or ()
    return humanize_warnings(_strings(values))


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
