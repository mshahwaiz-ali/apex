"""Canonical contracts for the trade-plan methodology pipeline.

These contracts provide one vocabulary across discovery, strategy routing,
execution geometry, scoring, rejection, presentation, and backtesting. They are
introduced without changing live trade behavior; existing layers can migrate to
them incrementally.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import StrEnum


class EvidenceFamily(StrEnum):
    STRUCTURE = "structure"
    TREND = "trend"
    MOMENTUM = "momentum"
    PARTICIPATION = "participation"
    VOLATILITY = "volatility"
    CANDLE = "candle"
    LIQUIDITY = "liquidity"
    DERIVATIVES = "derivatives"
    BROAD_CONTEXT = "broad_context"
    DATA_QUALITY = "data_quality"
    HISTORICAL = "historical"


class EvidenceEffect(StrEnum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    NEUTRAL = "neutral"


class EntryOpportunityType(StrEnum):
    IMMEDIATE = "immediate_entry"
    AGGRESSIVE = "aggressive_entry"
    PREFERRED_NEARBY = "preferred_nearby_entry"
    PULLBACK = "pullback_entry"
    RETEST = "retest_entry"
    RECLAIM = "reclaim_entry"
    REJECTION = "rejection_entry"
    DEVELOPING_FUTURE = "developing_future_entry"


class InvalidationRule(StrEnum):
    TOUCH = "touch"
    WICK = "wick"
    CLOSE = "close"


class TargetRole(StrEnum):
    TP1 = "tp1"
    TP2 = "tp2"
    TP3 = "tp3"
    RUNNER = "runner"


class HoldCategory(StrEnum):
    MICRO_SCALP = "micro_scalp"
    SCALP = "scalp"
    INTRADAY = "intraday"
    MULTI_SESSION = "multi_session"
    SWING = "swing"


class ConfidenceLabel(StrEnum):
    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class ConfidenceBasis(StrEnum):
    RULE_BASED = "rule_based"
    HISTORICALLY_CALIBRATED = "historically_calibrated"
    INSUFFICIENT_CALIBRATION = "insufficient_calibration"


class RejectionSeverity(StrEnum):
    HARD_BLOCKER = "hard_blocker"
    SOFT_PENALTY = "soft_penalty"


class RejectionCode(StrEnum):
    UNUSABLE_MARKET = "unusable_market"
    STALE_OR_INCOMPLETE_DATA = "stale_or_incomplete_data"
    STRUCTURALLY_INVALIDATED = "structurally_invalidated"
    WRONG_STRATEGY_FOR_STATE = "wrong_strategy_for_state"
    NO_DEFINABLE_INVALIDATION = "no_definable_invalidation"
    CORRUPT_STOP_GEOMETRY = "corrupt_stop_geometry"
    CLEARLY_MISSED_ENTRY = "clearly_missed_entry"
    NO_REALISTIC_TARGET_ROOM = "no_realistic_target_room"
    PATTERN_FAILED = "pattern_failed"
    DIRECT_STRUCTURAL_OPPOSITION = "direct_structural_opposition"
    LIQUIDATION_BUFFER_UNSAFE = "liquidation_buffer_unsafe"
    MILD_HTF_CONFLICT = "mild_htf_conflict"
    AVERAGE_PARTICIPATION = "average_participation"
    OPTIONAL_CONFLUENCE_MISSING = "optional_confluence_missing"
    SLIGHTLY_EXTENDED_ENTRY = "slightly_extended_entry"
    UNCERTAIN_DURATION = "uncertain_duration"
    WEAK_CANDLE_EVIDENCE = "weak_candle_evidence"
    REDUCED_TARGET_ROOM = "reduced_target_room"
    ELEVATED_VOLATILITY = "elevated_volatility"
    OPTIONAL_SIGNAL_CONTRADICTION = "optional_signal_contradiction"
    EXTREME_FUNDING = "extreme_funding"
    LOW_CONFIDENCE_DERIVATIVES_DATA = "low_confidence_derivatives_data"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _positive(name: str, value: float) -> None:
    _finite(name, value)
    if value <= 0.0:
        raise ValueError(f"{name} must be greater than zero")


def _unit_interval(name: str, value: float) -> None:
    _finite(name, value)
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between zero and one")


@dataclass(frozen=True, slots=True)
class EvidenceObservation:
    family: EvidenceFamily
    source: str
    normalized_strength: float
    freshness: float
    independence_group: str
    effect: EvidenceEffect
    reason: str

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("evidence source cannot be empty")
        if not self.independence_group.strip():
            raise ValueError("evidence independence group cannot be empty")
        if not self.reason.strip():
            raise ValueError("evidence reason cannot be empty")
        _unit_interval("evidence normalized strength", self.normalized_strength)
        _unit_interval("evidence freshness", self.freshness)


@dataclass(frozen=True, slots=True)
class Contradiction:
    code: str
    family: EvidenceFamily
    severity: float
    reason: str

    def __post_init__(self) -> None:
        if not self.code.strip() or not self.reason.strip():
            raise ValueError("contradiction code and reason cannot be empty")
        _unit_interval("contradiction severity", self.severity)


@dataclass(frozen=True, slots=True)
class EntryOpportunity:
    kind: EntryOpportunityType
    zone_low: float
    zone_high: float
    ideal_entry: float
    confirmation_level: float | None
    maximum_chase: float
    current_distance_percentage: float
    current_distance_atr: float
    quality: float
    reason: str
    expiry_bars: int

    def __post_init__(self) -> None:
        for name, value in (
            ("entry zone low", self.zone_low),
            ("entry zone high", self.zone_high),
            ("ideal entry", self.ideal_entry),
            ("maximum chase", self.maximum_chase),
        ):
            _positive(name, value)
        if self.zone_low > self.zone_high:
            raise ValueError("entry zone low cannot exceed entry zone high")
        if not self.zone_low <= self.ideal_entry <= self.zone_high:
            raise ValueError("ideal entry must lie inside the entry zone")
        if self.confirmation_level is not None:
            _positive("confirmation level", self.confirmation_level)
        for name, value in (
            ("current distance percentage", self.current_distance_percentage),
            ("current distance ATR", self.current_distance_atr),
        ):
            _finite(name, value)
            if value < 0.0:
                raise ValueError(f"{name} cannot be negative")
        _unit_interval("entry quality", self.quality)
        if not self.reason.strip():
            raise ValueError("entry reason cannot be empty")
        if self.expiry_bars <= 0:
            raise ValueError("entry expiry bars must be positive")


@dataclass(frozen=True, slots=True)
class StructuralInvalidation:
    price: float
    rule: InvalidationRule
    structure: str
    failure_event: str
    volatility_buffer: float
    estimated_slippage: float

    def __post_init__(self) -> None:
        _positive("invalidation price", self.price)
        if not self.structure.strip() or not self.failure_event.strip():
            raise ValueError("invalidation structure and failure event cannot be empty")
        for name, value in (
            ("volatility buffer", self.volatility_buffer),
            ("estimated slippage", self.estimated_slippage),
        ):
            _finite(name, value)
            if value < 0.0:
                raise ValueError(f"{name} cannot be negative")


@dataclass(frozen=True, slots=True)
class TargetCandidate:
    role: TargetRole
    price: float
    source: str
    expected_move_percentage: float
    risk_multiple: float
    conditional: bool = False

    def __post_init__(self) -> None:
        _positive("target price", self.price)
        if not self.source.strip():
            raise ValueError("target source cannot be empty")
        _positive("expected target move percentage", self.expected_move_percentage)
        _positive("target risk multiple", self.risk_multiple)


@dataclass(frozen=True, slots=True)
class DurationExpectation:
    category: HoldCategory
    expected_hold_min_seconds: int
    expected_hold_max_seconds: int
    expected_bars: int
    setup_expiry_bars: int
    expiry_reason: str

    def __post_init__(self) -> None:
        if self.expected_hold_min_seconds <= 0:
            raise ValueError("minimum expected hold must be positive")
        if self.expected_hold_max_seconds < self.expected_hold_min_seconds:
            raise ValueError("maximum expected hold cannot be below minimum")
        if self.expected_bars <= 0 or self.setup_expiry_bars <= 0:
            raise ValueError("expected bars and setup expiry bars must be positive")
        if not self.expiry_reason.strip():
            raise ValueError("duration expiry reason cannot be empty")


@dataclass(frozen=True, slots=True)
class ConfidenceAssessment:
    setup: ConfidenceLabel
    execution: ConfidenceLabel
    target: ConfidenceLabel
    data: ConfidenceLabel
    historical: ConfidenceLabel
    overall: ConfidenceLabel
    basis: ConfidenceBasis
    strongest_support: str
    strongest_contradiction: str | None
    missing_evidence: tuple[str, ...] = ()
    model_estimated_success_rate: float | None = None
    sample_size: int | None = None

    def __post_init__(self) -> None:
        if not self.strongest_support.strip():
            raise ValueError("confidence strongest support cannot be empty")
        if self.strongest_contradiction is not None and not self.strongest_contradiction.strip():
            raise ValueError("confidence contradiction cannot be blank")
        if self.model_estimated_success_rate is not None:
            if self.basis is not ConfidenceBasis.HISTORICALLY_CALIBRATED:
                raise ValueError("success rate requires historically calibrated confidence")
            _unit_interval("model estimated success rate", self.model_estimated_success_rate)
            if self.sample_size is None or self.sample_size <= 0:
                raise ValueError("calibrated confidence requires a positive sample size")
        elif self.sample_size is not None:
            raise ValueError("sample size requires a model estimated success rate")


@dataclass(frozen=True, slots=True)
class RejectionReason:
    code: RejectionCode
    severity: RejectionSeverity
    reason: str
    penalty: float = 0.0

    def __post_init__(self) -> None:
        if not self.reason.strip():
            raise ValueError("rejection reason cannot be empty")
        _unit_interval("rejection penalty", self.penalty)
        if self.severity is RejectionSeverity.HARD_BLOCKER and self.penalty != 0.0:
            raise ValueError("hard blockers are gates and cannot carry score penalties")


__all__ = [
    "ConfidenceAssessment",
    "ConfidenceBasis",
    "ConfidenceLabel",
    "Contradiction",
    "DurationExpectation",
    "EntryOpportunity",
    "EntryOpportunityType",
    "EvidenceEffect",
    "EvidenceFamily",
    "EvidenceObservation",
    "HoldCategory",
    "InvalidationRule",
    "RejectionCode",
    "RejectionReason",
    "RejectionSeverity",
    "StructuralInvalidation",
    "TargetCandidate",
    "TargetRole",
]
