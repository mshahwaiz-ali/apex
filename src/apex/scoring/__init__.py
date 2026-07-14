"""Deterministic Phase 5 scoring, ranking, conflict, and selection API."""

from apex.scoring.analysis import analyze_phase5
from apex.scoring.approval import (
    ApprovalReason,
    ApprovalReasonCode,
    SetupEligibility,
    StrategyApprovalDecision,
    evaluate_strategy_approval,
)
from apex.scoring.approval_overlay import apply_strategy_quality_gate
from apex.scoring.config import (
    DEFAULT_SCORING_CONFIG,
    PenaltyWeights,
    ScoringConfig,
    ScoringWeights,
    StrategyProfile,
)
from apex.scoring.contracts import (
    CandidateOutcome,
    ConflictSummary,
    DirectionalConsensus,
    Phase5AnalysisResult,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.scoring.quality_gate import (
    CandidateQualityGateDecision,
    QualityGateReason,
    QualityGateReasonCode,
    evaluate_candidate_quality_gate,
)

__all__ = [
    "DEFAULT_SCORING_CONFIG",
    "ApprovalReason",
    "ApprovalReasonCode",
    "CandidateOutcome",
    "CandidateQualityGateDecision",
    "ConflictSummary",
    "DirectionalConsensus",
    "PenaltyWeights",
    "Phase5AnalysisResult",
    "QualityGateReason",
    "QualityGateReasonCode",
    "RankedCandidate",
    "ScoreBreakdown",
    "ScoredCandidate",
    "ScoringConfig",
    "ScoringWeights",
    "SetupEligibility",
    "StrategyApprovalDecision",
    "StrategyProfile",
    "analyze_phase5",
    "apply_strategy_quality_gate",
    "evaluate_candidate_quality_gate",
    "evaluate_strategy_approval",
]
