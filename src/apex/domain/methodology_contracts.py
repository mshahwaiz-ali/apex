"""Typed methodology contracts for layered market state and score semantics.

These contracts are intentionally representation-only. They do not classify,
route, approve, reject, rank, or otherwise change candidate eligibility.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, fields
from enum import StrEnum
from typing import Any


class _LabelledEnum(StrEnum):
    @property
    def label(self) -> str:
        return _LABELS[type(self)][self]

    @classmethod
    def labels(cls) -> dict[str, str]:
        return {member.value: member.label for member in cls}


class ExecutionState(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    CLEAN = "clean"
    MIXED = "mixed"
    CHOPPY = "choppy"
    CHAOTIC = "chaotic"
    EXPANDING = "expanding"
    REVERSAL_TRANSITION = "reversal_transition"


class SetupState(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    TREND_CONTINUATION = "trend_continuation"
    PULLBACK = "pullback"
    BREAKOUT = "breakout"
    BREAKOUT_RETEST = "breakout_retest"
    RANGE = "range"
    REVERSAL_ATTEMPT = "reversal_attempt"
    REVERSAL_CONFIRMED = "reversal_confirmed"
    FAILED_BREAKOUT = "failed_breakout"
    FAILED_BREAKDOWN = "failed_breakdown"
    COMPRESSION = "compression"
    EXPANSION = "expansion"


class ContextState(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGE_BOUND = "range_bound"
    COMPRESSED = "compressed"
    EXPANDING = "expanding"
    EXHAUSTED_UP = "exhausted_up"
    EXHAUSTED_DOWN = "exhausted_down"
    TRANSITIONAL = "transitional"
    MIXED = "mixed"


class StructuralBias(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class RiskCondition(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    NORMAL = "normal"
    ELEVATED = "elevated"
    EXTREME = "extreme"
    STALE_DATA = "stale_data"
    THIN_LIQUIDITY = "thin_liquidity"
    WIDE_SPREAD = "wide_spread"
    VOLATILITY_SHOCK = "volatility_shock"
    EXECUTION_CHAOS = "execution_chaos"


class TimeframeRelationship(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    WITH_TREND = "with_trend"
    MIXED = "mixed"
    COUNTERTREND_SCALP = "countertrend_scalp"
    REVERSAL_ATTEMPT = "reversal_attempt"
    STRUCTURAL_REVERSAL_CONFIRMED = "structural_reversal_confirmed"
    DIRECT_STRUCTURAL_OPPOSITION = "direct_structural_opposition"


class RelationshipSeverity(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    NONE = "none"
    MILD = "mild"
    MODERATE = "moderate"
    STRONG = "strong"
    CRITICAL = "critical"


class HoldingHorizon(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    MICRO_SCALP = "micro_scalp"
    SCALP = "scalp"
    INTRADAY = "intraday"
    MULTI_HOUR = "multi_hour"
    SWING = "swing"
    RUNNER = "runner"


class ContinuationState(_LabelledEnum):
    UNAVAILABLE = "unavailable"
    FRESH_CONTINUATION = "fresh_continuation"
    MATURE_CONTINUATION = "mature_continuation"
    LATE_CHASE = "late_chase"
    EXHAUSTION_WARNING = "exhaustion_warning"
    FAILED_BREAKDOWN = "failed_breakdown"
    FAILED_BREAKOUT = "failed_breakout"
    REVERSAL_WATCH = "reversal_watch"


_LABELS: dict[type[_LabelledEnum], dict[_LabelledEnum, str]] = {
    ExecutionState: {
        ExecutionState.UNAVAILABLE: "Unavailable",
        ExecutionState.CLEAN: "Clean",
        ExecutionState.MIXED: "Mixed",
        ExecutionState.CHOPPY: "Choppy",
        ExecutionState.CHAOTIC: "Chaotic",
        ExecutionState.EXPANDING: "Expanding",
        ExecutionState.REVERSAL_TRANSITION: "Reversal transition",
    },
    SetupState: {
        SetupState.UNAVAILABLE: "Unavailable",
        SetupState.TREND_CONTINUATION: "Trend continuation",
        SetupState.PULLBACK: "Pullback",
        SetupState.BREAKOUT: "Breakout",
        SetupState.BREAKOUT_RETEST: "Breakout retest",
        SetupState.RANGE: "Range",
        SetupState.REVERSAL_ATTEMPT: "Reversal attempt",
        SetupState.REVERSAL_CONFIRMED: "Reversal confirmed",
        SetupState.FAILED_BREAKOUT: "Failed breakout",
        SetupState.FAILED_BREAKDOWN: "Failed breakdown",
        SetupState.COMPRESSION: "Compression",
        SetupState.EXPANSION: "Expansion",
    },
    ContextState: {
        ContextState.UNAVAILABLE: "Unavailable",
        ContextState.TRENDING_UP: "Trending up",
        ContextState.TRENDING_DOWN: "Trending down",
        ContextState.RANGE_BOUND: "Range bound",
        ContextState.COMPRESSED: "Compressed",
        ContextState.EXPANDING: "Expanding",
        ContextState.EXHAUSTED_UP: "Exhausted up",
        ContextState.EXHAUSTED_DOWN: "Exhausted down",
        ContextState.TRANSITIONAL: "Transitional",
        ContextState.MIXED: "Mixed",
    },
    StructuralBias: {
        StructuralBias.UNAVAILABLE: "Unavailable",
        StructuralBias.BULLISH: "Bullish",
        StructuralBias.BEARISH: "Bearish",
        StructuralBias.NEUTRAL: "Neutral",
        StructuralBias.MIXED: "Mixed",
    },
    RiskCondition: {
        RiskCondition.UNAVAILABLE: "Unavailable",
        RiskCondition.NORMAL: "Normal",
        RiskCondition.ELEVATED: "Elevated",
        RiskCondition.EXTREME: "Extreme",
        RiskCondition.STALE_DATA: "Stale data",
        RiskCondition.THIN_LIQUIDITY: "Thin liquidity",
        RiskCondition.WIDE_SPREAD: "Wide spread",
        RiskCondition.VOLATILITY_SHOCK: "Volatility shock",
        RiskCondition.EXECUTION_CHAOS: "Execution chaos",
    },
    TimeframeRelationship: {
        TimeframeRelationship.UNAVAILABLE: "Unavailable",
        TimeframeRelationship.WITH_TREND: "With trend",
        TimeframeRelationship.MIXED: "Mixed",
        TimeframeRelationship.COUNTERTREND_SCALP: "Countertrend scalp",
        TimeframeRelationship.REVERSAL_ATTEMPT: "Reversal attempt",
        TimeframeRelationship.STRUCTURAL_REVERSAL_CONFIRMED: ("Structural reversal confirmed"),
        TimeframeRelationship.DIRECT_STRUCTURAL_OPPOSITION: ("Direct structural opposition"),
    },
    RelationshipSeverity: {
        RelationshipSeverity.UNAVAILABLE: "Unavailable",
        RelationshipSeverity.NONE: "None",
        RelationshipSeverity.MILD: "Mild",
        RelationshipSeverity.MODERATE: "Moderate",
        RelationshipSeverity.STRONG: "Strong",
        RelationshipSeverity.CRITICAL: "Critical",
    },
    HoldingHorizon: {
        HoldingHorizon.UNAVAILABLE: "Unavailable",
        HoldingHorizon.MICRO_SCALP: "Micro scalp",
        HoldingHorizon.SCALP: "Scalp",
        HoldingHorizon.INTRADAY: "Intraday",
        HoldingHorizon.MULTI_HOUR: "Multi-hour",
        HoldingHorizon.SWING: "Swing",
        HoldingHorizon.RUNNER: "Runner",
    },
    ContinuationState: {
        ContinuationState.UNAVAILABLE: "Unavailable",
        ContinuationState.FRESH_CONTINUATION: "Fresh continuation",
        ContinuationState.MATURE_CONTINUATION: "Mature continuation",
        ContinuationState.LATE_CHASE: "Late chase",
        ContinuationState.EXHAUSTION_WARNING: "Exhaustion warning",
        ContinuationState.FAILED_BREAKDOWN: "Failed breakdown",
        ContinuationState.FAILED_BREAKOUT: "Failed breakout",
        ContinuationState.REVERSAL_WATCH: "Reversal watch",
    },
}


@dataclass(frozen=True, slots=True)
class LayeredStateSnapshot:
    execution_state: ExecutionState = ExecutionState.UNAVAILABLE
    setup_state: SetupState = SetupState.UNAVAILABLE
    context_state: ContextState = ContextState.UNAVAILABLE
    structural_bias: StructuralBias = StructuralBias.UNAVAILABLE
    risk_condition: RiskCondition = RiskCondition.UNAVAILABLE
    timeframe_relationship: TimeframeRelationship = TimeframeRelationship.UNAVAILABLE
    relationship_severity: RelationshipSeverity = RelationshipSeverity.UNAVAILABLE
    holding_horizon: HoldingHorizon = HoldingHorizon.UNAVAILABLE
    continuation_state: ContinuationState = ContinuationState.UNAVAILABLE

    def to_dict(self) -> dict[str, str]:
        return {field.name: getattr(self, field.name).value for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> LayeredStateSnapshot:
        return cls(
            execution_state=ExecutionState(
                payload.get("execution_state", ExecutionState.UNAVAILABLE)
            ),
            setup_state=SetupState(payload.get("setup_state", SetupState.UNAVAILABLE)),
            context_state=ContextState(payload.get("context_state", ContextState.UNAVAILABLE)),
            structural_bias=StructuralBias(
                payload.get("structural_bias", StructuralBias.UNAVAILABLE)
            ),
            risk_condition=RiskCondition(payload.get("risk_condition", RiskCondition.UNAVAILABLE)),
            timeframe_relationship=TimeframeRelationship(
                payload.get(
                    "timeframe_relationship",
                    TimeframeRelationship.UNAVAILABLE,
                )
            ),
            relationship_severity=RelationshipSeverity(
                payload.get(
                    "relationship_severity",
                    RelationshipSeverity.UNAVAILABLE,
                )
            ),
            holding_horizon=HoldingHorizon(
                payload.get("holding_horizon", HoldingHorizon.UNAVAILABLE)
            ),
            continuation_state=ContinuationState(
                payload.get(
                    "continuation_state",
                    ContinuationState.UNAVAILABLE,
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ScoreDimensions:
    pattern_confidence: float | None = None
    directional_alignment: float | None = None
    setup_quality: float | None = None
    execution_quality: float | None = None
    reward_quality: float | None = None
    timing_quality: float | None = None
    data_confidence: float | None = None
    overall_trade_quality: float | None = None
    rank_score: float | None = None

    def __post_init__(self) -> None:
        for field in fields(self):
            value = getattr(self, field.name)
            if value is None:
                continue
            if not math.isfinite(value):
                raise ValueError(f"{field.name} must be finite when provided")
            if not 0.0 <= value <= 100.0:
                raise ValueError(f"{field.name} must be between 0 and 100 when provided")

    def to_dict(self) -> dict[str, float | None]:
        return {field.name: getattr(self, field.name) for field in fields(self)}

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ScoreDimensions:
        return cls(**{field.name: payload.get(field.name) for field in fields(cls)})
