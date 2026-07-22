"""Candidate scoring, conflict resolution, and final selection orchestration."""

from __future__ import annotations

from apex.scoring.applicability import apply_strategy_applicability
from apex.scoring.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from apex.scoring.conflicts import resolve_conflicts
from apex.scoring.contracts import CandidateOutcome, CandidateSelectionResult
from apex.scoring.environment_route import EnvironmentRoute, apply_environment_route_alignment
from apex.scoring.ranking import rank_candidates
from apex.scoring.scorer import score_candidates
from apex.scoring.selection import (
    is_entry_status_executable,
    no_trade_reason,
    select_candidate,
    select_future_candidate,
)
from apex.strategies import classify_candidate_actionability
from apex.strategies.analysis import StrategyAnalysisResult


def analyze_candidate_selection(
    strategy_analysis: StrategyAnalysisResult,
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    environment_route: EnvironmentRoute | None = None,
) -> CandidateSelectionResult:
    """Score, rank, resolve, and select candidates without account-oriented gates."""

    scored = score_candidates(strategy_analysis.candidates, config=config)
    scored = apply_strategy_applicability(
        scored,
        applicability=strategy_analysis.strategy_applicability or {},
    )
    scored = apply_environment_route_alignment(scored, route=environment_route)
    initially_ranked = rank_candidates(
        scored,
        strategy_order=strategy_analysis.evaluated_strategies,
    )
    ranked, conflict_summary = resolve_conflicts(initially_ranked, config=config)
    selected = select_candidate(ranked, config=config)
    selected_future = select_future_candidate(ranked, config=config)
    rejected = tuple(item for item in ranked if item.outcome.value.startswith("rejected"))
    outcome_counts = {
        outcome.value: sum(item.outcome is outcome for item in ranked)
        for outcome in CandidateOutcome
    }
    return CandidateSelectionResult(
        symbol=strategy_analysis.symbol,
        decision_time=strategy_analysis.decision_time,
        all_scored_candidates=scored,
        ranked_candidates=ranked,
        rejected_candidates=rejected,
        conflict_summary=conflict_summary,
        directional_consensus=conflict_summary.directional_consensus,
        selected_candidate=selected,
        selected_future_candidate=selected_future,
        no_trade_reason=(
            None if selected is not None or selected_future is not None else no_trade_reason(ranked)
        ),
        evaluated_strategy_order=strategy_analysis.evaluated_strategies,
        configuration_id=config.identifier,
        metadata={
            "candidate_count": len(scored),
            "ranked_count": len(ranked),
            "rejected_count": len(rejected),
            "selected": selected is not None or selected_future is not None,
            "selected_executable_now": (
                selected is not None
                and is_entry_status_executable(classify_candidate_actionability(selected.candidate))
            ),
            "selected_future_setup": selected_future is not None,
            "minimum_accept_score": config.minimum_accept_score,
            "warning_accept_score": config.warning_accept_score,
            "terminal_outcome_count": sum(outcome_counts.values()),
            **{
                f"terminal_outcome_{outcome.value}_count": outcome_counts[outcome.value]
                for outcome in CandidateOutcome
            },
            "lineage_balanced": len(scored) == len(ranked) == sum(outcome_counts.values()),
            "config_hash": config.fingerprint(),
            "duplicate_cluster_count": len(conflict_summary.duplicate_groups),
            "decision_regime": strategy_analysis.decision_regime.value,
            "eligible_strategy_count": len(strategy_analysis.eligible_strategies or ()),
            "skipped_strategy_count": len(strategy_analysis.skipped_strategies or {}),
            "strategy_applicability_weighting_enabled": bool(
                strategy_analysis.strategy_applicability
            ),
            "environment_route_weighting_enabled": environment_route is not None,
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
