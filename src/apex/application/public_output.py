"""Canonical public serialization for Stage 3 discovery commands."""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from apex.application import decision_analysis as _decision
from apex.application.discovery_contracts import ScanResult

_LEGACY_PUBLIC_KEYS = frozenset({"near_current_entry", "precision_entry", "near_miss_state"})
_ACTIONABLE_STATUSES = frozenset({"READY_NOW", "AGGRESSIVE_NOW"})
_DEVELOPING_STATUSES = frozenset({"PULLBACK_PREFERRED", "WATCH_NEAR_ENTRY"})
_UNAVAILABLE_STATUSES = frozenset({"LATE_OR_CHASING", "INVALIDATED"})


def serialize_symbol_analysis(analysis: _decision.SymbolAnalysis) -> dict[str, Any]:
    """Return one discovery result without legacy entry-state overlays."""

    payload = _without_legacy_keys(_decision.serialize_symbol_analysis(analysis))
    setup =