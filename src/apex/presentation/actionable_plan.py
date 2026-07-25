"""Shared snapshot-plan hydration and ranking semantics for scan and analyze."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence

_ACTIONABLE_STATUSES = {
    "READY_NOW",
    "AGGRESSIVE_NOW",
    "PULLBACK_PREFERRED",
    "RETEST_PREFERRED",
    "RECLAIM_REQUIRED",
    "WAIT_FOR_RETEST",
    "WAIT_FOR_RECLAIM",
    "MISSED_ENTRY",
    "LATE_OR_CHASING",
}


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


def _walk(root: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    queue: deque[Mapping[str, object]] = deque((root,))
    seen: set[int] = set()
    found: list[Mapping[str, object]] = []
    while queue:
        current = queue.popleft()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        found.append(current)
        for value in current.values():
            if isinstance(value, Mapping):
                queue.append(value)
            elif isinstance(value, Sequence) and not isinstance(value, str | bytes):
                queue.extend(item for item in value if isinstance(item, Mapping))
    return tuple(found)


def _first_mapping(
    mappings: tuple[Mapping[str, object], ...],
    keys: tuple[str, ...],
) -> Mapping[str, object]:
    for mapping in mappings:
        for key in keys:
            candidate = _mapping(mapping.get(key))
            if candidate:
                return candidate
    return {}


def _first_value(
    mappings: tuple[Mapping[str, object], ...],
    keys: tuple[str, ...],
) -> object | None:
    for mapping in mappings:
        for key in keys:
            value = mapping.get(key)
            if value is not None and value != "":
                return value
    return None


def _normalise_entry(
    raw: Mapping[str, object],
    *,
    current_price: float | None,
) -> dict[str, object]:
    lower = _number(raw.get("lower") or raw.get("low") or raw.get("entry_low"))
    upper = _number(raw.get("upper") or raw.get("high") or raw.get("entry_high"))
    preferred = _number(
        raw.get("preferred")
        or raw.get("ideal")
        or raw.get("price")
        or raw.get("entry_price")
    )
    if lower is None and preferred is not None:
        lower = preferred
    if upper is None and preferred is not None:
        upper = preferred
    if preferred is None and lower is not None and upper is not None:
        preferred = (lower + upper) / 2.0

    entry = dict(raw)
    if current_price is not None:
        entry["current_price"] = current_price
    if lower is not None:
        entry["lower"] = lower
    if upper is not None:
        entry["upper"] = upper
    if preferred is not None:
        entry["preferred"] = preferred
    maximum_chase = _first_value((raw,), ("maximum_chase_price", "maximum_chase", "chase_limit"))
    if maximum_chase is not None:
        entry["maximum_chase_price"] = maximum_chase
    return entry


def _normalise_stop(raw: Mapping[str, object]) -> dict[str, object]:
    stop = dict(raw)
    price = _number(raw.get("price") or raw.get("stop_price") or raw.get("level"))
    if price is not None:
        stop["price"] = price
    return stop


def _normalise_targets(
    mappings: tuple[Mapping[str, object], ...],
    setup: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    direct = _mappings(setup.get("take_profits")) or _mappings(setup.get("targets"))
    if direct:
        return direct
    for mapping in mappings:
        direct = _mappings(mapping.get("take_profits")) or _mappings(mapping.get("targets"))
        if direct:
            return direct
    return ()


def _status(setup: Mapping[str, object]) -> str:
    return str(setup.get("entry_status") or setup.get("actionability_state") or "").upper()


def _default_trigger_type(status: str) -> str:
    if status in {"RECLAIM_REQUIRED", "WAIT_FOR_RECLAIM"}:
        return "reclaim_close"
    return "retest_hold"


def _reason(status: str) -> str:
    if status == "MISSED_ENTRY":
        return "Original entry was missed; use only the published re-entry zone after a fresh retest hold."
    if status in {"PULLBACK_PREFERRED", "LATE_OR_CHASING"}:
        return "Wait for price to return to the published entry zone; do not chase at CMP."
    if status in {"RECLAIM_REQUIRED", "WAIT_FOR_RECLAIM"}:
        return "Wait for a confirmed reclaim close through the published trigger level."
    return "Wait for the published entry zone to hold before entry."


def hydrate_actionable_setup(
    opportunity: Mapping[str, object],
    *,
    portfolio_cmp: object | None = None,
) -> dict[str, object]:
    """Preserve hidden geometry and publish a complete snapshot plan when defensible."""

    source = _mapping(opportunity.get("setup")) or _mapping(opportunity.get("developing_setup"))
    if not source:
        source = opportunity
    mappings = _walk(opportunity)
    setup = dict(source)

    current_price = _number(
        _mapping(source.get("entry")).get("current_price")
        or source.get("current_price")
        or opportunity.get("current_price")
        or opportunity.get("cmp")
        or portfolio_cmp
        or _first_value(mappings, ("current_price", "cmp", "mark_price", "ticker_price"))
    )

    raw_entry = _mapping(source.get("entry")) or _first_mapping(
        mappings,
        (
            "entry",
            "re_entry",
            "reentry",
            "re_entry_zone",
            "preferred_entry",
            "original_entry",
            "entry_zone",
        ),
    )
    entry = _normalise_entry(raw_entry, current_price=current_price)
    if entry:
        setup["entry"] = entry

    raw_stop = _mapping(source.get("stop_loss")) or _first_mapping(
        mappings,
        ("stop_loss", "post_entry_stop", "stop", "invalidation"),
    )
    stop = _normalise_stop(raw_stop)
    if stop:
        setup["stop_loss"] = stop

    targets = _normalise_targets(mappings, source)
    if targets:
        setup["take_profits"] = targets

    status = _status(setup)
    plan = dict(_mapping(source.get("conditional_plan")))
    if not plan:
        plan = dict(_first_mapping(mappings, ("conditional_plan", "activation_plan", "future_plan")))

    preferred = _number(entry.get("preferred"))
    if status in _ACTIONABLE_STATUSES and preferred is not None:
        trigger = dict(_mapping(plan.get("trigger")))
        if not trigger:
            trigger = {
                "type": _default_trigger_type(status),
                "level": preferred,
                "confirmation_timeframe": (
                    setup.get("confirmation_timeframe")
                    or _first_value(mappings, ("confirmation_timeframe", "entry_timeframe"))
                    or "5m"
                ),
                "condition": _reason(status),
            }
        plan["trigger"] = trigger
        plan.setdefault("reason_not_executable_now", _reason(status))
        plan.setdefault("recommended_order_intent", "alert_only")

        invalidation = dict(_mapping(plan.get("pre_entry_invalidation")))
        stop_price = _number(stop.get("price"))
        if not invalidation and stop_price is not None:
            invalidation = {"price": stop_price, "reason": "setup structure invalidated"}
        if invalidation:
            plan["pre_entry_invalidation"] = invalidation

    if plan:
        setup["conditional_plan"] = plan

    return setup


def plan_completeness(setup: Mapping[str, object]) -> int:
    """Return a stable completeness score without treating confidence as actionability."""

    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    plan = _mapping(setup.get("conditional_plan"))
    trigger = _mapping(plan.get("trigger"))
    score = 0
    score += 1 if _number(entry.get("current_price")) is not None else 0
    score += 2 if _number(entry.get("lower")) is not None and _number(entry.get("upper")) is not None else 0
    score += 1 if _number(entry.get("preferred")) is not None else 0
    score += 1 if _number(stop.get("price")) is not None else 0
    score += 2 if trigger and _number(trigger.get("level")) is not None else 0
    score += 1 if _mapping(plan.get("pre_entry_invalidation")) else 0
    return score


def plan_lane(setup: Mapping[str, object]) -> int:
    """Rank actionability before confidence for snapshot commands."""

    completeness = plan_completeness(setup)
    status = _status(setup)
    if setup.get("execution_allowed_now") is True and completeness >= 5:
        return 6
    if status in {"READY_NOW", "AGGRESSIVE_NOW"} and completeness >= 5:
        return 5
    if status in {
        "PULLBACK_PREFERRED",
        "RETEST_PREFERRED",
        "RECLAIM_REQUIRED",
        "WAIT_FOR_RETEST",
        "WAIT_FOR_RECLAIM",
    } and completeness >= 6:
        return 4
    if status in {"MISSED_ENTRY", "LATE_OR_CHASING"} and completeness >= 6:
        return 3
    if completeness >= 5:
        return 2
    return 1


def actionable_plan_available(setup: Mapping[str, object]) -> bool:
    """Incomplete summaries are diagnostics, not trade plans."""

    return plan_lane(setup) >= 2


__all__ = [
    "actionable_plan_available",
    "hydrate_actionable_setup",
    "plan_completeness",
    "plan_lane",
]
