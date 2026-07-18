"""Expose evidence-family independence without double-counting correlated signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from apex.application.methodology_evidence_aggregation import aggregate_evidence_families
from apex.application.methodology_snapshot import MethodologySnapshot


@dataclass(frozen=True, slots=True)
class EvidenceIndependenceSemantics:
    """Public interpretation of family support and independence-group diversity."""

    evidence_count: int
    family_count: int
    independence_group_count: int
    correlated_observation_count: int
    supporting_family_count: int
    contradicting_family_count