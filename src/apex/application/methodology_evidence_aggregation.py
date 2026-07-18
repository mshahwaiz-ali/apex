"""Aggregate canonical evidence without double-counting correlated observations."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from apex.application.methodology_contracts import (
    EvidenceEffect,
    EvidenceFamily,
    EvidenceObservation,
)


@dataclass(frozen=True, slots=True)
class EvidenceFamilyAggregate:
    family: EvidenceFamily
    support_score: float
    contradiction_score: float
    neutral_score: float
    net_score: float
    independence_groups: tuple[str, ...]
    observation_count: int
    strongest_support: str | None
    strongest_contradiction: str | None

