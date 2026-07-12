"""Phase 5 scoring, conflict resolution, and final selection orchestration."""

from __future__ import annotations

from apex.scoring.config import DEFAULT_SCORING_CONFIG, ScoringConfig
from apex.scoring.conflicts import resolve_conflicts
from apex.scoring.contracts import CandidateOutcome, Phase5AnalysisResult
from apex.scoring.ranking import rank_candidates
from apex.scoring.scorer import score_candidates
from apex.scoring.selection import no_trade_reason, select_candidate
from apex.strategies.analysis import Phase4AnalysisResult


def analyze_phase5(
    phase4: Phase4AnalysisResult,
    *,
    config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> Phase5AnalysisResult:
    """Consume immutable Phase 4 candidates and produce one deterministic decision."""

    scored = score_candidates(phase4.candidates, config=config)
    initially_ranked = rank_candidates(
        scored,
        strategy_order=phase4.evaluated_strategies,
    )
    ranked, conflict_summary = resolve_conflicts(initially_ranked, config=config)
    selected = select_candidate(ranked, config=config)
    rejected = tuple(item for item in ranked if item.outcome.value.startswith("rejected"))
    return Phase5AnalysisResult(
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
