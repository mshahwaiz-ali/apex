"""Presentation-only information architecture for Apex operator output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum
from numbers import Real


class ScanInformationSection(StrEnum):
    """Operator-facing scan sections required by the methodology plan."""

    ACTIONABLE_CMP = "actionable_cmp"
    NEARBY_LIMIT = "nearby_limit"
    MICRO_CONFIRMATION = "micro_confirmation"
    FOLLOW_UP_REVERSAL = "follow_up_reversal"
    WEAK_INVALID = "weak_invalid"


@dataclass(frozen=True, slots=True)
class ScanInformationGroups:
    """Stable presentation grouping without changing ranking or selection."""

    actionable_cmp: tuple[Mapping[str, object], ...]
    nearby_limit: tuple[Mapping[str, object], ...]
    micro_confirmation: tuple[Mapping[str, object], ...]
    follow_up_reversal: tuple[Mapping[str, object], ...]
    weak_invalid: tuple[Mapping[str, object], ...]

    @property
    def visible_count(self) -> int:
        return (
            len(self.actionable_cmp)
            + len(self.nearby_limit)
            + len(self.micro_confirmation)
            + len(self.follow_up_reversal)
        )


def partition_scan_results(
    results: Sequence[Mapping[str, object]],
) -> ScanInformationGroups:
    """Partition already-ranked results using presentation semantics only."""

    buckets: dict[ScanInformationSection, list[Mapping[str, object]]] = {
        section: [] for section in ScanInformationSection
    }
    for result in results:
        buckets[_classify(result)].append(result)
    return ScanInformationGroups(
        actionable_cmp=tuple(buckets[ScanInformationSection.ACTIONABLE_CMP]),
        nearby_limit=tuple(buckets[ScanInformationSection.NEARBY_LIMIT]),
        micro_confirmation=tuple(buckets[ScanInformationSection.MICRO_CONFIRMATION]),
        follow_up_reversal=tuple(buckets[ScanInformationSection.FOLLOW_UP_REVERSAL]),
        weak_invalid=tuple(buckets[ScanInformationSection.WEAK_INVALID]),
    )


def data_quality_warning(payload: Mapping[str, object]) -> str | None:
    """Return a compact truthful warning when methodology fields are unavailable."""

    completeness = _mapping(payload.get("methodology_completeness"))
    unavailable = _strings(completeness.get("unavailable_fields"))
    if unavailable:
        return f"Unavailable evidence: {', '.join(unavailable[:3])}"

    warning = payload.get("data_quality_warning")
    if isinstance(warning, str) and warning.strip():
        return warning.strip()

    evidence = _mapping(payload.get("market_evidence"))
    disposition = str(evidence.get("disposition") or "").strip().lower()
    if disposition == "insufficient":
        return "Required market evidence is stale or unavailable"
    if disposition == "degraded":
        return "Optional market evidence is incomplete"
    return None


def opportunity_map_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Summarize optional analysis opportunities without inventing missing data."""

    lines: list[str] = []
    for label, keys in (
        ("Current opportunity", ("setup",)),
        ("Nearby alternative", ("nearby_alternative", "alternative_setup")),
        ("Opposite follow-up", ("opposite_follow_up", "follow_up_setup")),
        ("Developing setup", ("developing_setup",)),
    ):
        value = _first_mapping(payload, keys)
        if not value:
            continue
        direction = str(value.get("direction") or "unknown").replace("_", " ").title()
        strategy = str(value.get("strategy") or "unknown").replace("_", " ").title()
        status = str(value.get("entry_status") or "unknown").replace("_", " ").title()
        lines.append(f"{label}: {direction} • {strategy} • {status}")
    return tuple(lines)


def diagnostic_summary_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Expose collision, lifecycle, runner, and data-quality diagnostics when present."""

    lines: list[str] = []
    for label, keys in (
        ("Collision", ("opportunity_collision", "collision_analysis")),
        ("Lifecycle", ("opportunity_lifecycle", "lifecycle_analysis")),
        ("Runner", ("runner_decision", "runner_lifecycle")),
    ):
        value = _first_mapping(payload, keys)
        if not value:
            continue
        state = (
            value.get("decision")
            or value.get("resolution")
            or value.get("stage")
            or value.get("state")
        )
        if state is not None:
            lines.append(f"{label}: {str(state).replace('_', ' ').title()}")

    warning = data_quality_warning(payload)
    if warning:
        lines.append(f"Data quality: {warning}")
    return tuple(lines)


def _classify(result: Mapping[str, object]) -> ScanInformationSection:
    setup = _mapping(result.get("setup")) or _mapping(result.get("developing_setup"))
    if not setup:
        return ScanInformationSection.WEAK_INVALID

    status = str(setup.get("entry_status") or "").upper()
    if status in {"INVALIDATED", "MISSED_ENTRY", "LATE_OR_CHASING", "EXPIRED"}:
        return ScanInformationSection.WEAK_INVALID

    role = " ".join(
        str(setup.get(key) or "").lower()
        for key in ("opportunity_role", "sequence_role", "setup_role")
    )
    strategy = str(setup.get("strategy") or "").lower()
    if "follow" in role or "reversal" in role or "reversal" in strategy:
        return ScanInformationSection.FOLLOW_UP_REVERSAL

    if status in {"READY_NOW", "AGGRESSIVE_NOW"}:
        return ScanInformationSection.ACTIONABLE_CMP

    activation_text = " ".join(
        (
            str(setup.get("entry_mode") or ""),
            str(setup.get("activation_type") or ""),
            *_strings(setup.get("warnings")),
        )
    ).lower()
    if any(token in activation_text for token in ("confirm", "reclaim", "close")):
        return ScanInformationSection.MICRO_CONFIRMATION

    if status in {
        "PULLBACK_PREFERRED",
        "RETEST_PREFERRED",
        "WAIT_FOR_RETEST",
        "WAIT_FOR_RECLAIM",
        "RECLAIM_REQUIRED",
        "APPROACHING_ENTRY",
    }:
        return ScanInformationSection.NEARBY_LIMIT

    return ScanInformationSection.FOLLOW_UP_REVERSAL


def _first_mapping(
    payload: Mapping[str, object],
    keys: tuple[str, ...],
) -> Mapping[str, object]:
    for key in keys:
        value = _mapping(payload.get(key))
        if value:
            return value
    return {}


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def multi_timeframe_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Return concise timeframe state lines from any supported public shape."""

    source = (
        _mapping(payload.get("multi_timeframe_map"))
        or _mapping(payload.get("timeframe_map"))
        or _mapping(_mapping(payload.get("focused_analysis")).get("timeframe_map"))
    )
    lines: list[str] = []
    for timeframe, raw in source.items():
        item = _mapping(raw)
        if item:
            structure = (
                item.get("structure") or item.get("trend") or item.get("state") or item.get("bias")
            )
            momentum = item.get("momentum")
            note = item.get("summary") or item.get("reason")
            parts = [
                str(value).replace("_", " ").title()
                for value in (structure, momentum, note)
                if value not in {None, ""}
            ]
            if parts:
                lines.append(f"{timeframe}: {' • '.join(parts[:3])}")
        elif raw not in {None, ""}:
            lines.append(f"{timeframe}: {str(raw).replace('_', ' ').title()}")
    return tuple(lines)


def rationale_lines(
    payload: Mapping[str, object],
    setup: Mapping[str, object],
) -> tuple[str, ...]:
    """Expose entry, stop, target, and chase rationale without recomputation."""

    del payload
    entry = _mapping(setup.get("entry"))
    stop = _mapping(setup.get("stop_loss"))
    lines: list[str] = []

    for label, value in (
        (
            "Entry rationale",
            entry.get("rationale")
            or setup.get("entry_rationale")
            or setup.get("activation_reason"),
        ),
        (
            "Stop rationale",
            stop.get("single_buffer_rationale")
            or stop.get("rationale")
            or setup.get("stop_rationale"),
        ),
        (
            "Target rationale",
            setup.get("target_rationale") or setup.get("target_path_reason"),
        ),
        (
            "Chase boundary",
            entry.get("maximum_chase_rationale") or setup.get("maximum_chase_rationale"),
        ),
    ):
        if value not in {None, ""}:
            lines.append(f"{label}: {str(value).strip()}")
    return tuple(lines)


def evidence_contradiction_lines(
    payload: Mapping[str, object],
    setup: Mapping[str, object],
) -> tuple[str, ...]:
    """Return concise supporting and contradictory evidence."""

    lines: list[str] = []
    evidence = _strings(setup.get("evidence")) or _strings(payload.get("evidence"))
    contradictions = (
        _strings(setup.get("contradictions"))
        or _strings(setup.get("warnings"))
        or _strings(payload.get("contradictions"))
    )
    lines.extend(f"Support: {item}" for item in evidence[:4])
    lines.extend(f"Contradiction: {item}" for item in contradictions[:4])
    return tuple(lines)


def rejected_candidate_lines(payload: Mapping[str, object]) -> tuple[str, ...]:
    """Summarize rejected candidates under explain mode only."""

    candidates = (
        _mappings(payload.get("rejected_candidates"))
        or _mappings(payload.get("candidate_rejections"))
        or _mappings(payload.get("rejections"))
    )
    lines: list[str] = []
    for candidate in candidates[:8]:
        direction = str(candidate.get("direction") or "unknown").replace("_", " ").title()
        strategy = str(candidate.get("strategy") or "unknown").replace("_", " ").title()
        reason = (
            candidate.get("reason")
            or candidate.get("rejection_reason")
            or candidate.get("primary_blocker")
            or "No reason supplied"
        )
        lines.append(f"{direction} • {strategy}: {reason}")
    return tuple(lines)


def entry_distance_label(setup: Mapping[str, object]) -> str | None:
    """Format serialized entry distance without inventing geometry."""

    entry = _mapping(setup.get("entry"))
    value = entry.get("distance_from_current")
    if not isinstance(value, Real) or isinstance(value, bool):
        return None

    unit = str(entry.get("distance_unit") or "").strip().lower()
    numeric = float(value)
    if unit in {"fraction", "ratio"}:
        return f"{numeric * 100:.2f}%"
    if unit in {"percent", "percentage", "%"}:
        return f"{numeric:.2f}%"
    return f"{numeric:.4f}"


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = [
    "ScanInformationGroups",
    "ScanInformationSection",
    "data_quality_warning",
    "diagnostic_summary_lines",
    "entry_distance_label",
    "evidence_contradiction_lines",
    "multi_timeframe_lines",
    "opportunity_map_lines",
    "partition_scan_results",
    "rationale_lines",
    "rejected_candidate_lines",
]
