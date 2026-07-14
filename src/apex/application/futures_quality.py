"""Application helper for the N3 futures standard-mode quality pass."""

from __future__ import annotations

from pathlib import Path

from apex.config import StrategyApprovalConfig, load_strategy_approval_config
from apex.domain import RiskMode
from apex.scoring import Phase5AnalysisResult, ScoringConfig, analyze_phase5
from apex.scoring.config import DEFAULT_SCORING_CONFIG
from apex.strategies.analysis import Phase4AnalysisResult

DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH = Path("config/strategy_approval.yaml")


def analyze_futures_phase5(
    phase4: Phase4AnalysisResult,
    *,
    risk_mode: RiskMode = RiskMode.STANDARD,
    scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    strategy_approval_config: StrategyApprovalConfig | None = None,
) -> Phase5AnalysisResult:
    """Run Phase 5 with explicit N3 strategy-quality approval enabled."""

    approval_config = strategy_approval_config or load_strategy_approval_config(
        DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH
    )
    return analyze_phase5(
        phase4,
        config=scoring_config,
        risk_mode=risk_mode,
        strategy_approval_config=approval_config,
    )
