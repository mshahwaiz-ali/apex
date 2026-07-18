"""Project selected Phase 5 candidate evidence into methodology contracts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from apex.application.methodology_contracts import (
    Contradiction,
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)

_SUPPORT_STRENGTH = 0.6
_CONTRADICTION_STRENGTH = 0.55
_NEUTRAL_STRENGTH = 0.4


def selected_candidate_methodology_evidence(
    phase5_diagnostics: Mapping[str, Any] | None,
    *,
    candidate_id: str,