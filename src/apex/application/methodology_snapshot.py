"""Aggregate canonical methodology state for one analyzed candidate or symbol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    Contradiction,
    DurationExpectation,
    EntryOpportunity,
    EvidenceObservation,
    RejectionReason,
    RejectionSeverity,
    StructuralInvalidation,
    TargetCandidate,
)
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    MarketStateClassification,
    SetupMaturity,
)


@dataclass(frozen=True, slots=True)
class MethodologySnapshot:
    """Normalized