"""Application helper for discovery candidate selection."""

from __future__ import annotations

from apex.scoring import CandidateSelectionResult, ScoringConfig, analyze_candidate_selection
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.scoring.environment_route import EnvironmentRoute
from apex.strategies.analysis import StrategyAnalysisResult


def analyze_futures_phase5(
    strategy_analysis: StrategyAnalysisResult,
    *,
    scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    environment_route: EnvironmentRoute | None = None,
) -> CandidateSelectionResult:
    """Run wallet-independent candidate scoring, ranking, and selection."""

    return analyze_candidate_selection(
        strategy_analysis,
        config=scoring_config,
        environment_route=environment_route,
    )
