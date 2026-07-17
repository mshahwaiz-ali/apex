"""Candidate scoring, conflict resolution, and final selection orchestration."""

from __future__ import annotations

from pathlib import Path

from apex.config.strategy_approval import (
    StrategyApprovalConfig,
    load_strategy_approval_config,
)
from apex.domain import RiskMode
from apex.scoring.applicability import apply_strategy_applicability
from apex.scoring.approval_overlay import apply_strategy_quality_gate
from apex.scoring.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from apex.scoring.conflicts import resolve_conflicts
from apex.scoring.contracts import CandidateOutcome, CandidateSelectionResult
from apex.scoring.environment_route import EnvironmentRoute, apply_environment_route_alignment
from apex.scoring.ranking import rank_candidates
from apex.scoring.scorer import score_candidates
from apex.scoring.selection import no_trade_reason, select_candidate
from apex.strategies.analysis import Phase4AnalysisResult

DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH = Path("config/strategy_approval.yaml")


def analyze_candidate_selection(
    phase4: Phase4AnalysisResult,
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    risk_mode: RiskMode = RiskMode.STANDARD,
    strategy_approval_config: StrategyApprovalConfig | None = None,
    apply_strategy_quality: bool = False,
    environment_route: EnvironmentRoute | None = None,
) -> CandidateSelectionResult:
    """Consume immutable strategy candidates and produce one deterministic decision.

    Raw candidate scoring does not apply the strategy-quality
    gate unless ``apply_strategy_quality=True``. Futures orchestration enables the
    gate explicitly through its futures candidate-selection wrapper.
    """

    approval_config = strategy_approval_config
    if apply_strategy_quality and approval_config is None:
        approval_config = load_strategy_approval_config(DEFAULT_STRATEGY_APPROVAL_CONFIG_PATH)
    if not apply_strategy_quality and strategy_approval_config is not None:
        raise ValueError(
            "strategy approval configuration cannot be supplied when quality gating is disabled"
        )

    scored = score_candidates(phase4.candidates, config=config)
    scored = apply_strategy_applicability(
        scored,
        applicability=phase4.strategy_applicability or {},
    )
    scored = apply_environment_route_alignment(scored, route=environment_route)
    initially_ranked = rank_candidates(
        scored,
        strategy_order=phase4.evaluated_strategies,
    )
    ranked, conflict_summary = resolve_conflicts(initially_ranked, config=config)
    if approval_config is not None:
        ranked = apply_strategy_quality_gate(
            ranked,
            risk_mode=risk_mode,
            config=approval_config,
        )
    selected = select_candidate(ranked, config=config)
    rejected = tuple(item for item in ranked if item.outcome.value.startswith("rejected"))
    return CandidateSelectionResult(
        symbol=phase4.symbol,
        decision_time=phase4.decision_time,
        all_scored_candidates=scored,
        ranked_candidates=ranked,
        rejected_candidates=rejected,
        conflict_summary=conflict_summary,
        directional_consensus=conflict_summary.directional_consensus,
        selected_candidate=selected,
        no_trade_reason=None if selected is not None else no_trade_reason(ranked),
        evaluated_strategy_order=phase4.evaluated_strategies,
        configuration_id=config.identifier,
        metadata={
            "candidate_count": len(scored),
            "rejected_count": len(rejected),
            "selected": selected is not None,
            "config_hash": config.fingerprint(),
            "duplicate_cluster_count": len(conflict_summary.duplicate_groups),
            "decision_regime": phase4.decision_regime.value,
            "eligible_strategy_count": len(phase4.eligible_strategies or ()),
            "skipped_strategy_count": len(phase4.skipped_strategies or {}),
            "strategy_applicability_weighting_enabled": bool(
                phase4.strategy_applicability
            ),
            "environment_route_weighting_enabled": environment_route is not None,
            "strategy_quality_gate_enabled": approval_config is not None,
            "strategy_quality_risk_mode": risk_mode.value if approval_config is not None else "",
            "accepted_count": sum(
                item.outcome
                in {
                    CandidateOutcome.ACCEPTED,
                    CandidateOutcome.ACCEPTED_WITH_WARNING,
                }
                for item in ranked
            ),
        },
    )
