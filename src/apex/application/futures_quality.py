"""Application helper for the futures standard-mode quality pass."""

from __future__ import annotations

from pathlib import Path

from apex.application.futures_risk_mode import current_futures_risk_mode
from apex.config import StrategyApprovalConfig, load_strategy_approval_config
from apex.domain import RiskMode
from apex.scoring import CandidateSelectionResult, ScoringConfig, analyze_candidate_selection
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.scoring.environment_route import EnvironmentRoute
from apex.strategies.analysis import StrategyAnalysisResult

DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH = Path("config/strategy_approval.yaml")


def analyze_futures_phase5(
    strategy_analysis: StrategyAnalysisResult,
    *,
    risk_mode: RiskMode | None = None,
    scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    strategy_approval_config: StrategyApprovalConfig | None = None,
    environment_route: EnvironmentRoute | None = None,
) -> CandidateSelectionResult:
    """Run candidate selection with explicit strategy-quality approval enabled."""

    selected_risk_mode = risk_mode or current_futures_risk_mode()
    approval_config = strategy_approval_config or load_strategy_approval_config(
        DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH
    )
    return analyze_candidate_selection(
        strategy_analysis,
        config=scoring_config,
        risk_mode=selected_risk_mode,
        strategy_approval_config=approval_config,
        apply_strategy_quality=True,
        environment_route=environment_route,
    )
