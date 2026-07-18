"""Operator-facing scan grouping independent from selection approval."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum


class ScanGroup(StrEnum):
    READY = "ready_now"
    AGGRESSIVE = "aggressive_now"
    CONDITIONAL = "conditional_entry"
    DEVELOPING = "developing_setup"
    UNAVAILABLE = "late_or_invalidated"
    NO_SETUP = "no_setup"


@dataclass(frozen=True, slots=True)
class GroupedScanResults:
    ready: tuple[Mapping[str, object], ...]
    aggressive: tuple[Mapping[str, object], ...]
    conditional: tuple[Mapping[str, object], ...]
    developing: tuple[Mapping[str, object], ...]
    unavailable: tuple[Mapping[str, object], ...]
    no_setup: tuple[Mapping[str, object], ...]

    @property
    def counts(self) -> Mapping[str, int]:
        return {
            ScanGroup.READY.value: len(self.ready),
            ScanGroup.AGGRESSIVE.value: len(self.aggressive),
            ScanGroup.CONDITIONAL.value: len(self.conditional),
            ScanGroup.DEVELOPING.value: len(self.developing),
            ScanGroup.UNAVAILABLE.value: len(self.unavailable),
            ScanGroup.NO_SETUP.value: len(self.no_setup),
        }


def group_scan_results(
    results: Sequence[Mapping[str, object]],
) -> GroupedScanResults:
    """Classify scan rows by actual entry state, not score acceptance alone."""

    buckets: dict[ScanGroup, list[Mapping[str, object]]] = {group: [] for group in ScanGroup}
    for result in results:
        group = classify_scan_result(result)
        buckets[group].append(result)
    return GroupedScanResults(
        ready=tuple(buckets[ScanGroup.READY]),
        aggressive=tuple(buckets[ScanGroup.AGGRESSIVE]),
        conditional=tuple(buckets[ScanGroup.CONDITIONAL]),
        developing=tuple(buckets[ScanGroup.DEVELOPING]),
        unavailable=tuple(buckets[ScanGroup.UNAVAILABLE]),
        no_setup=tuple(buckets[ScanGroup.NO_SETUP]),
    )


def classify_scan_result(result: Mapping[str, object]) -> ScanGroup:
    """Return one stable operator group for a discovery result."""

    setup = _mapping(result.get("setup")) or _mapping(result.get("developing_setup"))
    if not setup:
        return ScanGroup.NO_SETUP

    status = str(setup.get("entry_status") or "").upper()
    if status == "READY_NOW":
        return ScanGroup.READY
    if status == "AGGRESSIVE_NOW":
        return ScanGroup.AGGRESSIVE
    if status in {
        "PULLBACK_PREFERRED",
        "RETEST_PREFERRED",
        "RECLAIM_REQUIRED",
        "WAIT_FOR_RETEST",
        "WAIT_FOR_RECLAIM",
    }:
        return ScanGroup.CONDITIONAL
    if status in {"LATE_OR_CHASING", "MISSED_ENTRY", "INVALIDATED"}:
        return ScanGroup.UNAVAILABLE
    return ScanGroup.DEVELOPING


def flatten_existing_scan_groups(
    payload: Mapping[str, object],
) -> tuple[Mapping[str, object], ...]:
    """Read canonical results while remaining compatible with older payloads."""

    direct = _mappings(payload.get("results"))
    if direct:
        return direct

    ordered_keys = (
        "actionable_setups",
        "developing_setups",
        "unavailable_setups",
        "no_trade_results",
    )
    flattened: list[Mapping[str, object]] = []
    seen: set[tuple[str, str, str]] = set()
    for key in ordered_keys:
        for item in _mappings(payload.get(key)):
            setup = _mapping(item.get("setup")) or _mapping(item.get("developing_setup"))
            identity = (
                str(item.get("symbol") or ""),
                str(setup.get("strategy") or ""),
                str(setup.get("direction") or ""),
            )
            if identity in seen:
                continue
            seen.add(identity)
            flattened.append(item)
    return tuple(flattened)


def _mapping(value: object) -> Mapping[str, object]:
    return value if isinstance(value, Mapping) else {}


def _mappings(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(value, str | bytes):
        return ()
    return tuple(item for item in value if isinstance(item, Mapping))


__all__ = [
    "GroupedScanResults",
    "ScanGroup",
    "classify_scan_result",
    "flatten_existing_scan_groups",
    "group_scan_results",
]
