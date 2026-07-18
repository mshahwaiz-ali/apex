"""Optionally enforce the methodology verdict for the selected discovery setup."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.application.methodology_selected_strategy_verdict import (
    SelectedStrategyVerdict,
    SelectedStrategyVerdictState,
)


class MethodologyGateMode(StrEnum):
    SHADOW = "shadow"
    ENFORCE = "enforce"


@dataclass(frozen=True, slots=True)
class MethodologyGateResult:
    assessment: DiscoveryAssessment
    mode: MethodologyGateMode
    changed