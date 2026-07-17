"""Public strategy-analysis compatibility surface."""

from apex.strategies.applicability import (
    StrategyApplicability,
    StrategyApplicabilityState,
    build_strategy_applicability,
)
from apex.strategies.orchestration import (
    CandidateActionability,
    StrategyAnalysisResult,
    SuppressedStrategyCandidate,
    analyze_strategies,
)

__all__ = [
    "CandidateActionability",
    "StrategyAnalysisResult",
    "StrategyApplicability",
    "StrategyApplicabilityState",
    "SuppressedStrategyCandidate",
    "analyze_strategies",
    "build_strategy_applicability",
]
