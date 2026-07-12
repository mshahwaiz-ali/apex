"""Deterministic strategy candidate generation."""

from apex.strategies.analysis import Phase4AnalysisResult, analyze_phase4
from apex.strategies.breakout_continuation import generate_breakout_continuation_candidates
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import (
    EntryMode,
    EntryZone,
    InvalidationConcept,
    InvalidationType,
    RawQualityMetrics,
    StrategyEvidence,
    StrategyType,
    TargetConcept,
    TargetLevel,
    TargetType,
    TradeCandidate,
    TradeDirection,
)
from apex.strategies.entry import EntryReference, EntrySelectionConfig, select_entry_zone
from apex.strategies.liquidity_reversal import generate_liquidity_reversal_candidates
from apex.strategies.momentum_continuation import generate_momentum_continuation_candidates
from apex.strategies.range_reversal import generate_range_reversal_candidates
from apex.strategies.registry import STRATEGY_REGISTRY, StrategyGenerator
from apex.strategies.trend_pullback import generate_trend_pullback_candidates

__all__ = [
    "STRATEGY_REGISTRY",
    "EntryMode",
    "EntryReference",
    "EntrySelectionConfig",
    "EntryZone",
    "FeatureSnapshot",
    "InvalidationConcept",
    "InvalidationType",
    "Phase4AnalysisResult",
    "RawQualityMetrics",
    "StrategyContext",
    "StrategyEvidence",
    "StrategyGenerator",
    "StrategyType",
    "TargetConcept",
    "TargetLevel",
    "TargetType",
    "TimeframeContext",
    "TimeframeRole",
    "TradeCandidate",
    "TradeDirection",
    "analyze_phase4",
    "generate_breakout_continuation_candidates",
    "generate_liquidity_reversal_candidates",
    "generate_momentum_continuation_candidates",
    "generate_range_reversal_candidates",
    "generate_trend_pullback_candidates",
    "select_entry_zone",
]
