"""Immutable contracts for deterministic strategy candidate generation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType

from apex.domain.methodology_contracts import (
    LayeredStateSnapshot,
    ScoreDimensions,
)
from apex.strategies.strategy_types import StrategyType


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class EntryMode(StrEnum):
    MARKET_NEAR = "market_near"
    PULLBACK = "pullback"
    RETEST = "retest"
    SWEEP_RECOVERY = "sweep_recovery"
    MOMENTUM_CONTINUATION = "momentum_continuation"
    SCALED_ENTRY = "scaled_entry"


_STRATEGY_BASE_EXPIRY_SECONDS: dict[StrategyType, int] = {
    StrategyType.MOMENTUM_SCALP: 300,
    StrategyType.MOMENTUM_BREAKOUT: 900,
    StrategyType.BREAKOUT_CONTINUATION: 1_200,
    StrategyType.COMPRESSION_EXPANSION: 1_200,
    StrategyType.BREAKOUT_RETEST: 2_700,
    StrategyType.FIRST_PULLBACK_CONTINUATION: 2_700,
    StrategyType.TREND_PULLBACK: 3_600,
    StrategyType.VWAP_RECLAIM_REJECTION: 1_800,
    StrategyType.RANGE_REVERSAL: 2_700,
    StrategyType.FAILED_BREAKOUT_REVERSAL: 1_800,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: 1_800,
    StrategyType.EXHAUSTION_REVERSAL: 900,
}

_ENTRY_MODE_EXPIRY_MULTIPLIER: dict[EntryMode, float] = {
    EntryMode.MARKET_NEAR: 0.50,
    EntryMode.MOMENTUM_CONTINUATION: 0.75,
    EntryMode.SCALED_ENTRY: 1.00,
    EntryMode.PULLBACK: 1.25,
    EntryMode.RETEST: 1.50,
    EntryMode.SWEEP_RECOVERY: 1.00,
}

_STRATEGY_EXPIRY_BARS: dict[StrategyType, int] = {
    StrategyType.MOMENTUM_BREAKOUT: 3,
    StrategyType.BREAKOUT_CONTINUATION: 3,
    StrategyType.BREAKOUT_RETEST: 6,
    StrategyType.FIRST_PULLBACK_CONTINUATION: 8,
    StrategyType.TREND_PULLBACK: 8,
    StrategyType.COMPRESSION_EXPANSION: 6,
    StrategyType.RANGE_REVERSAL: 6,
    StrategyType.FAILED_BREAKOUT_REVERSAL: 6,
    StrategyType.LIQUIDITY_REJECTION_REVERSAL: 6,
    StrategyType.VWAP_RECLAIM_REJECTION: 6,
    StrategyType.MOMENTUM_SCALP: 3,
    StrategyType.EXHAUSTION_REVERSAL: 6,
}


def candidate_expiry_seconds(
    *,
    strategy: StrategyType,
    entry_mode: EntryMode,
) -> int:
    "Return deterministic setup validity from strategy and entry type."

    base = _STRATEGY_BASE_EXPIRY_SECONDS.get(strategy, 900)
    multiplier = _ENTRY_MODE_EXPIRY_MULTIPLIER.get(entry_mode, 1.0)
    return max(180, round(base * multiplier))


def candidate_expiry_bars(strategy: StrategyType) -> int:
    """Return the canonical setup-frame expiry budget."""

    return _STRATEGY_EXPIRY_BARS[strategy]


class InvalidationType(StrEnum):
    STRUCTURAL = "structural"
    LIQUIDITY = "liquidity"
    VOLATILITY = "volatility"
    MOMENTUM_FAILURE = "momentum_failure"


class TargetType(StrEnum):
    STRUCTURAL = "structural"
    LIQUIDITY = "liquidity"
    RANGE = "range"
    EXPANSION = "expansion"
    PARTIAL = "partial"


class CandidateLifecycleStatus(StrEnum):
    ACTIVE = "active"
    EXPIRED = "expired"
    INVALIDATED = "invalidated"
    COOLDOWN = "cooldown"


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _positive(name: str, value: float) -> None:
    _finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _unit_interval(name: str, value: float) -> None:
    _finite(name, value)
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between zero and one")


def _aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class EntryZone:
    lower: float
    upper: float
    preferred: float
    current_price: float
    distance_from_current: float
    atr_distance: float
    estimated_move_missed: float
    location_quality: float
    mode: EntryMode
    rationale: tuple[str, ...]
    is_extended: bool = False
    max_chase_price: float | None = None
    expires_after_seconds: int | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("entry lower", self.lower),
            ("entry upper", self.upper),
            ("entry preferred", self.preferred),
            ("current price", self.current_price),
        ):
            _positive(name, value)
        if self.lower > self.upper:
            raise ValueError("entry lower cannot exceed entry upper")
        if not self.lower <= self.preferred <= self.upper:
            raise ValueError("preferred entry must lie inside the entry zone")
        for name, value in (
            ("distance from current", self.distance_from_current),
            ("ATR distance", self.atr_distance),
            ("estimated move missed", self.estimated_move_missed),
        ):
            _finite(name, value)
            if value < 0:
                raise ValueError(f"{name} cannot be negative")
        _unit_interval("location quality", self.location_quality)
        if not self.rationale:
            raise ValueError("entry rationale cannot be empty")
        if self.max_chase_price is not None:
            _positive("maximum chase price", self.max_chase_price)
        if self.expires_after_seconds is not None and self.expires_after_seconds <= 0:
            raise ValueError("entry expiry must be positive when provided")


@dataclass(frozen=True, slots=True)
class InvalidationConcept:
    kind: InvalidationType
    price: float
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive("invalidation price", self.price)
        if not self.rationale:
            raise ValueError("invalidation rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class TargetLevel:
    kind: TargetType
    price: float
    label: str
    rationale: tuple[str, ...]

    def __post_init__(self) -> None:
        _positive("target price", self.price)
        if not self.label.strip():
            raise ValueError("target label cannot be empty")
        if not self.rationale:
            raise ValueError("target rationale cannot be empty")


@dataclass(frozen=True, slots=True)
class TargetConcept:
    levels: tuple[TargetLevel, ...]

    def __post_init__(self) -> None:
        if not self.levels:
            raise ValueError("at least one target level is required")
        labels = tuple(level.label for level in self.levels)
        if len(set(labels)) != len(labels):
            raise ValueError("target labels must be unique")


@dataclass(frozen=True, slots=True)
class StrategyEvidence:
    supporting: tuple[str, ...]
    contradictions: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    feature_references: tuple[str, ...] = ()
    structure_references: tuple[str, ...] = ()
    liquidity_references: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.supporting:
            raise ValueError("supporting evidence cannot be empty")
        for name, values in (
            ("supporting evidence", self.supporting),
            ("contradictions", self.contradictions),
            ("warnings", self.warnings),
            ("feature references", self.feature_references),
            ("structure references", self.structure_references),
            ("liquidity references", self.liquidity_references),
        ):
            if len(set(values)) != len(values):
                raise ValueError(f"{name} must not contain duplicates")


@dataclass(frozen=True, slots=True)
class CandidateLifecycle:
    status: CandidateLifecycleStatus = CandidateLifecycleStatus.ACTIVE
    cooldown_key: str = ""
    expires_after_seconds: int = 900
    expires_after_bars: int = 6
    invalidation_price: float | None = None
    invalidation_reason: str = ""

    def __post_init__(self) -> None:
        if self.expires_after_seconds <= 0:
            raise ValueError("candidate expiry must be positive")
        if self.expires_after_bars <= 0:
            raise ValueError("candidate bar expiry must be positive")
        if self.invalidation_price is not None:
            _positive("candidate lifecycle invalidation price", self.invalidation_price)
        if self.status is CandidateLifecycleStatus.INVALIDATED and not self.invalidation_reason:
            raise ValueError("invalidated lifecycle requires an invalidation reason")


@dataclass(frozen=True, slots=True)
class RawQualityMetrics:
    trend_alignment: float
    structure_quality: float
    entry_quality: float
    momentum_quality: float
    volume_quality: float
    liquidity_quality: float
    target_space_quality: float
    extension_penalty: float = 0.0
    conflict_penalty: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "trend_alignment",
            "structure_quality",
            "entry_quality",
            "momentum_quality",
            "volume_quality",
            "liquidity_quality",
            "target_space_quality",
        ):
            _unit_interval(name.replace("_", " "), getattr(self, name))
        for name in ("extension_penalty", "conflict_penalty"):
            _unit_interval(name.replace("_", " "), getattr(self, name))


@dataclass(frozen=True, slots=True)
class TradeCandidate:
    symbol: str
    strategy: StrategyType
    direction: TradeDirection
    decision_time: datetime
    entry: EntryZone
    invalidation: InvalidationConcept
    targets: TargetConcept
    quality: RawQualityMetrics
    evidence: StrategyEvidence
    metadata: Mapping[str, str | int | float | bool]
    entry_opportunities: tuple[EntryZone, ...] = ()
    lifecycle: CandidateLifecycle | None = None
    provisional: bool = False
    layered_state: LayeredStateSnapshot = field(default_factory=LayeredStateSnapshot)
    score_dimensions: ScoreDimensions = field(default_factory=ScoreDimensions)

    def __post_init__(self) -> None:
        if not self.symbol.strip():
            raise ValueError("candidate symbol cannot be empty")
        _aware("candidate decision time", self.decision_time)
        if self.direction is TradeDirection.LONG:
            if self.invalidation.price >= self.entry.lower:
                raise ValueError("long invalidation must be below the entry zone")
            if any(level.price <= self.entry.upper for level in self.targets.levels):
                raise ValueError("long targets must be above the entry zone")
        else:
            if self.invalidation.price <= self.entry.upper:
                raise ValueError("short invalidation must be above the entry zone")
            if any(level.price >= self.entry.lower for level in self.targets.levels):
                raise ValueError("short targets must be below the entry zone")
        opportunities = self.entry_opportunities or (self.entry,)
        if self.entry not in opportunities:
            opportunities = (self.entry, *opportunities)
        deduplicated: list[EntryZone] = []
        seen: set[tuple[float, float, float, EntryMode]] = set()
        for opportunity in opportunities:
            key = (
                round(opportunity.lower, 12),
                round(opportunity.upper, 12),
                round(opportunity.preferred, 12),
                opportunity.mode,
            )
            if key in seen:
                continue
            seen.add(key)
            if self.direction is TradeDirection.LONG:
                if self.invalidation.price >= opportunity.lower:
                    raise ValueError("long invalidation must be below every entry opportunity")
                if any(level.price <= opportunity.upper for level in self.targets.levels):
                    raise ValueError("long targets must be above every entry opportunity")
            else:
                if self.invalidation.price <= opportunity.upper:
                    raise ValueError("short invalidation must be above every entry opportunity")
                if any(level.price >= opportunity.lower for level in self.targets.levels):
                    raise ValueError("short targets must be below every entry opportunity")
            deduplicated.append(opportunity)
        object.__setattr__(self, "entry_opportunities", tuple(deduplicated))

        metadata = dict(self.metadata)
        for metadata_key, value in metadata.items():
            if not metadata_key.strip():
                raise ValueError("metadata keys cannot be empty")
            if isinstance(value, float):
                _finite(f"metadata {metadata_key}", value)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))
        if self.lifecycle is None:
            object.__setattr__(
                self,
                "lifecycle",
                CandidateLifecycle(
                    cooldown_key=(
                        f"{self.symbol}:{self.strategy.value}:{self.direction.value}:"
                        f"{round(self.entry.preferred, 8)}"
                    ),
                    expires_after_seconds=(
                        self.entry.expires_after_seconds
                        or candidate_expiry_seconds(
                            strategy=self.strategy,
                            entry_mode=self.entry.mode,
                        )
                    ),
                    expires_after_bars=candidate_expiry_bars(self.strategy),
                    invalidation_price=self.invalidation.price,
                    invalidation_reason="candidate invalidation price is breached",
                ),
            )
