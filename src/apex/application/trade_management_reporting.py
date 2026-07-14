"""Human-readable reporting for canonical trade-management plans."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


def format_trade_management_plan(plan: Mapping[str, Any]) -> str:
    """Render one serialized trade-management plan as operational instructions."""

    entry = _mapping(plan, "entry")
    protection = _mapping(plan, "initial_protection")
    targets = _sequence_of_mappings(plan, "targets")
    stop_rules = _sequence_of_mappings(plan, "stop_management")
    emergency_rules = _sequence_of_mappings(plan, "emergency_exits")

    lines = [
        "Trade management:",
        f"Current action: {plan.get('current_action', 'UNKNOWN')}",
        (
            "Entry: "
            f"{entry.get('action', 'UNKNOWN')} via {entry.get('order_type', 'UNKNOWN')} "
            f"at {float(entry.get('zone_low', 0.0)):.4f}-"
            f"{float(entry.get('zone_high', 0.0)):.4f}; "
            f"ideal={float(entry.get('ideal_entry', 0.0)):.4f}; "
            f"max_chase={float(entry.get('maximum_chase_price', 0.0)):.4f}"
        ),
        (
            "Protection: "
            f"stop={float(protection.get('stop_loss_price', 0.0)):.4f}; "
            f"risk={float(protection.get('risk_percentage', 0.0)):.2f}% "
            f"({float(protection.get('risk_amount', 0.0)):.4f}); "
            f"qty={float(protection.get('quantity', 0.0)):.8f}; "
            f"notional={float(protection.get('notional', 0.0)):.4f}; "
            f"margin={float(protection.get('margin', 0.0)):.4f}; "
            f"leverage={float(protection.get('leverage', 0.0)):.2f}x"
        ),
    ]
    for target in targets:
        lines.append(
            "Target "
            f"{target.get('label', '?')}: {float(target.get('price', 0.0)):.4f} | "
            f"close={float(target.get('close_percentage', 0.0)):.2f}% | "
            f"cumulative={float(target.get('cumulative_close_percentage', 0.0)):.2f}% | "
            f"R={float(target.get('expected_r_multiple', 0.0)):.2f}"
        )
    for rule in stop_rules:
        lines.append(f"Stop rule: {rule.get('instruction', '')}")
    for rule in emergency_rules:
        lines.append(f"Emergency: {rule.get('condition', '')}")
    for condition in entry.get("cancellation_conditions", ()):
        lines.append(f"Cancel entry: {condition}")
    return "\n".join(lines)


def _mapping(payload: Mapping[str, Any], key: str) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ValueError(f"trade management field {key} must be an object")
    return value


def _sequence_of_mappings(
    payload: Mapping[str, Any],
    key: str,
) -> tuple[Mapping[str, Any], ...]:
    value = payload.get(key, ())
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"trade management field {key} must be a list")
    if any(not isinstance(item, Mapping) for item in value):
        raise ValueError(f"trade management field {key} must contain objects")
    return tuple(item for item in value if isinstance(item, Mapping))
