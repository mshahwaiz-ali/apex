"""Describe whether canonical methodology values are native, derived, or projected."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from apex.application.methodology_snapshot import MethodologySnapshot


class MethodologyValueSource(StrEnum):
    """Origin of a canonical methodology field."""

    NATIVE = "native"
    DERIVED = "derived"
    COMPATIBILITY_PROJECTION = "compatibility_projection"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class MethodologyFieldProvenance:
    """Explain where one methodology field came from without implying certainty."""

    field: str
    source: MethodologyValueSource
    reason: str

    def __post_init__(self) -> None:
        if not self.field.strip():
            raise ValueError("methodology provenance field cannot be empty")
        if not self.reason.strip():
            raise ValueError("methodology provenance reason cannot be empty")


_CANONICAL_FIELDS = (
    "market_usability",
    "market_state",
    "setup_maturity",
    "confirmation_policy",
    "evidence",
    "contradictions",
    "entry_opportunities",
    "invalidation",
    "targets",
    "duration",
    "confidence",
    "rejections",
)


def derive_methodology_provenance(
    *,
    stored_methodology: MethodologySnapshot | None,
    projected: MethodologySnapshot,
) -> tuple[MethodologyFieldProvenance, ...]:
    """Return deterministic provenance for every canonical methodology field.

    Stored non-empty values are native. Values absent from the stored snapshot but
    present after projection are compatibility projections or deterministic
    derivations. Missing values remain explicitly unavailable and never become a
    fabricated zero, neutral score, or hard rejection.
    """

    items: list[MethodologyFieldProvenance] = []
    for field in _CANONICAL_FIELDS:
        stored_value = None if stored_methodology is None else getattr(stored_methodology, field)
        projected_value = getattr(projected, field)
        if _is_present(stored_value):
            source = MethodologyValueSource.NATIVE
            reason = "value was supplied by the native methodology pipeline"
        elif not _is_present(projected_value):
            source = MethodologyValueSource.UNAVAILABLE
            reason = "the current analysis does not provide this methodology value"
        elif field in {"market_usability", "market_state", "setup_maturity", "confirmation_policy"}:
            source = MethodologyValueSource.DERIVED
            reason = "value was deterministically derived from existing canonical analysis state"
        else:
            source = MethodologyValueSource.COMPATIBILITY_PROJECTION
            reason = "value was projected from the existing selected setup for compatibility"
        items.append(MethodologyFieldProvenance(field=field, source=source, reason=reason))
    return tuple(items)


def methodology_provenance_payload(
    items: tuple[MethodologyFieldProvenance, ...],
) -> dict[str, dict[str, Any]]:
    """Serialize provenance keyed by canonical field name."""

    return {
        item.field: {
            "source": item.source.value,
            "reason": item.reason,
            "available": item.source is not MethodologyValueSource.UNAVAILABLE,
        }
        for item in items
    }


def methodology_completeness_payload(
    items: tuple[MethodologyFieldProvenance, ...],
) -> dict[str, Any]:
    """Summarize coverage without presenting it as strategy quality or probability."""

    available = tuple(item for item in items if item.source is not MethodologyValueSource.UNAVAILABLE)
    native = tuple(item for item in items if item.source is MethodologyValueSource.NATIVE)
    unavailable = tuple(item for item in items if item.source is MethodologyValueSource.UNAVAILABLE)
    return {
        "field_count": len(items),
        "available_field_count": len(available),
        "native_field_count": len(native),
        "unavailable_fields": [item.field for item in unavailable],
        "complete": not unavailable,
        "interpretation": "metadata coverage only; not trade quality or win probability",
    }


def _is_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, tuple | list | dict | set | frozenset):
        return bool(value)
    return True


__all__ = [
    "MethodologyFieldProvenance",
    "MethodologyValueSource",
    "derive_methodology_provenance",
    "methodology_completeness_payload",
    "methodology_provenance_payload",
]
