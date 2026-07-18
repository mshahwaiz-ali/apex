"""Build canonical methodology snapshots from existing selected candidates."""

from __future__ import annotations

from apex.application.methodology_adapters import strategy_evidence_observations
from apex.application.methodology_contracts import (
    ConfidenceAssessment,
    ConfidenceBasis,
    ConfidenceLabel,
    Contradiction,
    DurationExpectation,
    EntryOpportunity,
    EntryOpportunityType,
    EvidenceFamily,
    HoldCategory,
    InvalidationRule,
    StructuralInvalidation,
    TargetCandidate,
