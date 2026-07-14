"""Phase 5 scoring, conflict resolution, and final selection orchestration."""

from __future__ import annotations

from pathlib import Path

from apex.config.strategy_approval import (
    StrategyApprovalConfig,
    load_strategy_approval_config,
)
from apex.domain import RiskMode
from apex.scoring.approval_overlay import apply_strategy_quality_gate
from apex.scoring.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from apex.scoring.conflicts import resolve_conflicts
from apex.scoring.contracts import