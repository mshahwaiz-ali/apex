"""Deterministic methodology-segment metrics for chronological calibration records."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

_SEGMENT_DIMENSIONS = (
    "strategy",
    "lane",
    "direction",
    "timeframe_relationship",
    "continuation_state",
    "execution_state",
)


def methodology_segment_metrics(
    records: Sequence[Mapping[str, object]],
) -> dict[str, list[dict[str, object]]]:
    grouped: dict[str, dict[str, list[Mapping[str, object]]]] = {
        dimension: defaultdict(list) for dimension in _SEGMENT_DIMENSIONS
    }
    for record in records:
        layered_state = _mapping(record.get("layered_state"))
        values = {
            "strategy": _segment_value(record.get("strategy")),
            "lane": _segment_value(record.get("lane")),
            "direction": _segment_value(record.get("direction")),
            "timeframe_relationship": _segment_value(layered_state.get("timeframe_relationship")),
            "continuation_state": _segment_value(
                record.get("continuation_state") or layered_state.get("continuation_state")
            ),
            "execution_state": _segment_value(layered_state.get("execution_state")),
        }
        for dimension, value in values.items():
            grouped[dimension][value].append(record)

    return {
        dimension: [
            _segment_payload(value, grouped[dimension][value])
            for value in sorted(grouped[dimension])
        ]
        for dimension in _SEGMENT_DIMENSIONS
    }


def _segment_payload(
    value: str,
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    outcomes = tuple(_mapping(record.get("future_replay")) for record in records)
    realized_values: list[float] = []
    for item in outcomes:
        realized_value = item.get("realized_r_multiple")
        if isinstance(realized_value, int | float):
            realized_values.append(float(realized_value))
    realized = tuple(realized_values)
    resolved = tuple(
        str(item.get("outcome"))
        for item in outcomes
        if item.get("outcome") not in {None, "no_signal"}
    )
    wins = sum(outcome == "target" for outcome in resolved)
    losses = sum(outcome == "stop" for outcome in resolved)
    missed = sum(outcome == "missed_entry" for outcome in resolved)
    invalidated = sum(
        str(record.get("replay_reason_code", "")).endswith("invalidated") for record in records
    )
    return {
        "segment": value,
        "sample_size": len(records),
        "resolved_outcome_count": len(resolved),
        "win_count": wins,
        "loss_count": losses,
        "no_signal_count": sum(item.get("outcome") == "no_signal" for item in outcomes),
        "missed_entry_count": missed,
        "invalidation_count": invalidated,
        "win_rate": wins / len(resolved) if resolved else None,
        "expectancy_r": sum(realized) / len(realized) if realized else None,
        "calibration_authoritative": False,
    }


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _segment_value(value: object) -> str:
    if value is None:
        return "unavailable"
    text = str(value).strip()
    return text or "unavailable"


__all__ = ["methodology_segment_metrics"]
