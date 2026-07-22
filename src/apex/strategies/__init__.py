"""Deterministic Stage 3 strategy candidate generation."""

from apex.strategies.actionability import (
    best_entry_status,
    classify_candidate_actionability,
)
from apex.strategies.analysis import (
    CandidateActionability,
    StrategyAnalysisResult,
    StrategyApplicability,
    StrategyApplicabilityState,
    SuppressedStrategyCandidate,
    analyze_strategies,
    build_strategy_applicability,
)
from apex.strategies.breakout_continuation import generate_breakout_continuation_candidates
from apex.strategies.breakout_retest import generate_breakout_retest_candidates
from apex.strategies.compression_expansion import (
    generate_compression_expansion_candidates,
)
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
    timeframe_role_sort_key,
)
from apex.strategies.contracts import (
    CandidateLifecycle,
    CandidateLifecycleStatus,
    EntryMode,
    EntryOpportunityHorizon,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import EntryReference, EntrySelectionConfig, select_entry_zone
from apex.strategies.entry_status import ENTRY_STATUS_PRECEDENCE, EntryStatus
from apex.strategies.evidence import (
    NormalizedStrategyEvidence,
    StrategyEvidenceKind,
    normalize_strategy_evidence,
    strategy_evidence_payload,
    strategy_evidence_summary,
)
from apex.strategies.exhaustion_reversal import generate_exhaustion_reversal_candidates
from apex.strategies.failed_breakout_reversal import (
    generate_failed_breakout_reversal_candidates,
)
from apex.strategies.first_pullback_continuation import (
    generate_first_pullback_continuation_candidates,
)
from apex.strategies.liquidity_rejection_reversal import (
    generate_liquidity_rejection_reversal_candidates,
)
from apex.strategies.momentum_breakout import generate_momentum_breakout_candidates
from apex.strategies.momentum_scalp import generate_momentum_scalp_candidates
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.registry import STRATEGY_REGISTRY, StrategyGenerator
from apex.strategies.strategy_types import CanonicalStrategyFamily, StrategyType
from apex.strategies.trend_pullback import generate_trend_pullback_candidates
from apex.strategies.vwap_reclaim_rejection import (
    generate_vwap_reclaim_rejection_candidates,
)

__all__ = [
    "ENTRY_STATUS_PRECEDENCE",
    "STRATEGY_REGISTRY",
    "CandidateActionability",
    "CandidateLifecycle",
    "CandidateLifecycleStatus",
    "CanonicalStrategyFamily",
    "EntryMode",
    "EntryOpportunityHorizon",
    "EntryReference",
    "EntrySelectionConfig",
    "EntryStatus",
    "EntryZone",
    "FeatureSnapshot",
    "InvalidationConcept",
    "InvalidationType",
    "NormalizedStrategyEvidence",
    "RawQualityMetrics",
    "StrategyAnalysisResult",
    "StrategyApplicability",
    "StrategyApplicabilityState",
    "StrategyContext",
    "StrategyEvidence",
    "StrategyEvidenceKind",
    "StrategyGenerator",
    "StrategyType",
    "SuppressedStrategyCandidate",
    "TargetConcept",
    "TargetLevel",
    "TargetType",
    "TimeframeContext",
    "TimeframeRole",
    "TradeCandidate",
    "TradeDirection",
    "analyze_strategies",
    "best_entry_status",
    "build_strategy_applicability",
    "classify_candidate_actionability",
    "generate_breakout_continuation_candidates",
    "generate_breakout_retest_candidates",
    "generate_compression_expansion_candidates",
    "generate_exhaustion_reversal_candidates",
    "generate_failed_breakout_reversal_candidates",
    "generate_first_pullback_continuation_candidates",
    "generate_liquidity_rejection_reversal_candidates",
    "generate_momentum_breakout_candidates",
    "generate_momentum_scalp_candidates",
    "generate_range_reversal_candidates",
    "generate_trend_pullback_candidates",
    "generate_vwap_reclaim_rejection_candidates",
    "normalize_strategy_evidence",
    "select_entry_zone",
    "strategy_evidence_payload",
    "strategy_evidence_summary",
    "timeframe_role_sort_key",
]
