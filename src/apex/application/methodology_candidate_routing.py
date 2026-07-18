"""Apply methodology strategy decisions to generated candidates before ranking."""

from __future__ import annotations

from dataclasses import dataclass, replace

from apex.application.methodology_selected_strategy_gate import MethodologyGateMode
from apex.application.methodology_strategy_enforcement import (
    StrategyEnforcementAction,
    StrategyEnforcementDecision,
)
from apex.strategies.analysis import StrategyAnalysisResult, SuppressedStrategyCandidate
from apex.strategies.strategy_types import StrategyType


@dataclass(frozen=True, slots=True)
class MethodologyCandidateRoutingResult:
    """Candidate-routing outcome with deterministic audit metadata."""

    analysis: StrategyAnalysisResult
    mode: MethodologyGateMode
    suppressed_candidate_count: int
    suppressed_strategies: tuple[StrategyType, ...]
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.suppressed_candidate_count < 0:
            raise ValueError("suppressed candidate count cannot be negative")
        if len(set(self.suppressed_strategies))