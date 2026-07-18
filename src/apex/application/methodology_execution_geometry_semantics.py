"""Interpret entry and invalidation geometry without overstating execution readiness."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.discovery_contracts import DiscoverySetup
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class ExecutionGeometrySemantics:
    """Truthful execution interpretation for native and compatibility geometry."""

    setup_available: bool
    canonical_entry_available: bool
    canonical_invalidation_available: bool
    compatibility_entry_available: bool
    compatibility_stop_available: bool
    execution_ready