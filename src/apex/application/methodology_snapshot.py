"""Aggregate canonical methodology state for one analyzed candidate or symbol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.market_usability import (
    MarketUsabilityAssessment,
    market_usability_payload,
)
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
from apex.application.methodology_evidence_aggregation import (
    aggregate_evidence_families,
    evidence_family_aggregate_payload,
)
from apex.application.methodology_selected_entry_contracts import SelectedEntryDecision
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,