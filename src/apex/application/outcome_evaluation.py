"""Manual outcome annotations for persisted discovery records."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any, cast

OUTCOME_EVALUATION_SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class ManualOutcome:
    """One operator-supplied observation about a prior discovery result."""

    evaluated_at: datetime
    immediate_entry_reached: bool | None = None
    preferred_entry_reached: bool | None = None
    maximum_favorable_excursion: float | None = None
    maximum_adverse_excursion: float | None = None
    tp1_hit: bool | None = None
    tp2_hit: bool | None = None
    tp3_hit: bool | None = None
    stop_hit: bool | None = None
    time_to_target_seconds: float | None = None
    time_to_invalidation_seconds: float | None = None
    best_reward_multiple: float | None = None
    notes: str = ""

    def __post_init__(self) -> None:
        if self.evaluated_at.tzinfo is None or self.evaluated_at.utcoffset() is None:
            raise ValueError("outcome evaluation timestamp must be timezone-aware")
        for name in (
            "maximum_favorable_excursion",
            "maximum_adverse_excursion",
            "time_to_target_seconds",
            "time_to_invalidation_seconds",
            "best_reward_multiple",
        ):
            value = getattr(self, name)
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name.replace('_', ' ')} must be finite")
        for name in ("time_to_target_seconds", "time_to_invalidation_seconds"):
            value = getattr(self, name)
            if value is not None and value < 0.0:
                raise ValueError(f"{name.replace('_', ' ')} cannot be negative")


def append_manual_outcome(
    record: Mapping[str, Any],
    outcome: ManualOutcome,
) -> dict[str, Any]:
    """Return a copied record with one immutable manual outcome annotation appended."""

    updated = _copy_mapping(record)
    analysis_id = updated.get("analysis_id")
    if not isinstance(analysis_id, str) or not analysis_id.strip():
        raise ValueError("manual outcome requires a persisted analysis record identity")
    existing = updated.get("manual_outcomes", [])
    if not isinstance(existing, list):
        raise ValueError("manual outcomes must be stored as a list")
    annotation = asdict(outcome)
    annotation["evaluated_at"] = outcome.evaluated_at.astimezone(UTC).isoformat()
    annotation["schema_version"] = OUTCOME_EVALUATION_SCHEMA_VERSION
    updated["manual_outcomes"] = [*existing, annotation]
    return updated


def _copy_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    return cast(dict[str, Any], {key: _copy_value(item) for key, item in value.items()})


def _copy_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _copy_mapping(value)
    if isinstance(value, list):
        return [_copy_value(item) for item in value]
    return value


__all__ = [
    "OUTCOME_EVALUATION_SCHEMA_VERSION",
    "ManualOutcome",
    "append_manual_outcome",
]
