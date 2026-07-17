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
from apex.scoring.forward_approval import (
    ForwardApprovalReason,
    ForwardApprovalReasonCode,
    ForwardEvidenceAwareStrategyApprovalDecision,
    ForwardPaperEvidenceAttachment,
    ForwardPaperValidationView,
    evaluate_strategy_approval_with_forward_paper_evidence,
)
from apex.scoring.historical_approval import (
    EvidenceAwareStrategyApprovalDecision,
    HistoricalApprovalReason,
    HistoricalApprovalReasonCode,
    HistoricalEdgeValidationView,
    HistoricalEvidenceAttachment,
    evaluate_strategy_approval_with_historical_evidence,
)
from apex.scoring.rank_score import (
    RANK_SCORE_WEIGHTS,
    CandidateScoreDimensions,
    final_rank_score,
    rank_penalty_score,
    score_dimensions,
    unpenalized_rank_score,
)
from apex.scoring.quality_gate import (
    CandidateQualityGateDecision,
    QualityGateReason,
    QualityGateReasonCode,
    evaluate_candidate_quality_gate,
)
from apex.scoring.setup_segment import (
    SetupSegmentContext,
    SetupSegmentIdentity,
    score_band_for,
)

__all__ = [
    "DEFAULT_SCORING_CONFIG",
    "ApprovalReason",
    "ApprovalReasonCode",
    "CandidateOutcome",
    "CandidateQualityGateDecision",
    "CandidateScoreDimensions",
    "ConflictSummary",
    "DirectionalConsensus",
    "EvidenceAwareStrategyApprovalDecision",
    "ForwardApprovalReason",
    "ForwardApprovalReasonCode",
    "ForwardEvidenceAwareStrategyApprovalDecision",
    "ForwardPaperEvidenceAttachment",
    "ForwardPaperValidationView",
    "HistoricalApprovalReason",
    "HistoricalApprovalReasonCode",
    "HistoricalEdgeValidationView",
    "HistoricalEvidenceAttachment",
    "PenaltyWeights",
    "Phase5AnalysisResult",
    "QualityGateReason",
    "QualityGateReasonCode",
    "RANK_SCORE_WEIGHTS",
    "RankedCandidate",
    "ScoreBreakdown",
    "ScoredCandidate",
    "ScoringConfig",
    "ScoringWeights",
    "SetupEligibility",
    "SetupSegmentContext",
    "SetupSegmentIdentity",
    "StrategyApprovalDecision",
    "StrategyProfile",
    "analyze_phase5",
    "apply_strategy_quality_gate",
    "evaluate_candidate_quality_gate",
    "final_rank_score",
    "rank_penalty_score",
    "evaluate_strategy_approval",
    "evaluate_strategy_approval_with_forward_paper_evidence",
    "evaluate_strategy_approval_with_historical_evidence",
    "score_band_for",
    "score_dimensions",
    "unpenalized_rank_score",
]
