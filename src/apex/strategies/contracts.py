"""Immutable contracts for deterministic strategy candidate generation."""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class TradeDirection(StrEnum):
    LONG = "long"
    SHORT = "short"


class StrategyType(StrEnum):
    TREND_PULLBACK = "trend_pullback"
    BREAKOUT_CONTINUATION = "breakout_continuation"
    LIQUIDITY_REVERSAL = "liquidity_reversal"
    RANGE_REVERSAL = "range_reversal"
    MOMENTUM_CONTINUATION = "momentum_continuation"


class EntryMode(StrEnum):
    MARKET_NEAR = "market_near"
    PULLBACK = "pullback"
    RETEST = "retest"
    SWEEP_RECOVERY = "sweep_recovery"
    MOMENTUM_CONTINUATION = "momentum_continuation"
    SCALED_ENTRY = "scaled_entry"


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
    provisional: bool = False

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
        metadata = dict(self.metadata)
        for key, value in metadata.items():
            if not key.strip():
                raise ValueError("metadata keys cannot be empty")
            if isinstance(value, float):
                _finite(f"metadata {key}", value)
        object.__setattr__(self, "metadata", MappingProxyType(metadata))
