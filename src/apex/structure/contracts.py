"""Immutable contracts for deterministic market-structure analysis."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SwingType(StrEnum):
    HIGH = "high"
    LOW = "low"


class PivotStatus(StrEnum):
    CONFIRMED = "confirmed"
    DEVELOPING = "developing"


class ComparisonPolicy(StrEnum):
    STRICT = "strict"
    NON_STRICT = "non_strict"


class TrendDirection(StrEnum):
    STRONG_BULLISH = "strong_bullish"
    BULLISH = "bullish"
    WEAK_BULLISH = "weak_bullish"
    RANGE = "range"
    WEAK_BEARISH = "weak_bearish"
    BEARISH = "bearish"
    STRONG_BEARISH = "strong_bearish"
    TRANSITION = "transition"
    UNCERTAIN = "uncertain"


class BreakDirection(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class BreakQuality(StrEnum):
    WICK_ONLY = "wick_only"
    WEAK = "weak"
    VALID = "valid"
    STRONG = "strong"
    FAILED = "failed"


class ConfirmationStatus(StrEnum):
    CONFIRMED = "confirmed"
    DEVELOPING = "developing"
    REJECTED = "rejected"


class LevelRole(StrEnum):
    SUPPORT = "support"
    RESISTANCE = "resistance"


class LevelStatus(StrEnum):
    ACTIVE = "active"
    BROKEN = "broken"
    FLIPPED = "flipped"


class RangeBreakoutState(StrEnum):
    NONE = "none"
    BULLISH = "bullish"
    BEARISH = "bearish"
    FALSE_BULLISH = "false_bullish"
    FALSE_BEARISH = "false_bearish"


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


def _require_positive(name: str, value: float) -> None:
    _require_finite(name, value)
    if value <= 0:
        raise ValueError(f"{name} must be greater than zero")


def _require_aware(name: str, value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{name} must be timezone-aware")


@dataclass(frozen=True, slots=True)
class SwingPoint:
    index: int
    time: datetime
    price: float
    kind: SwingType
    status: PivotStatus
    left_window: int
    right_window: int

    def __post_init__(self) -> None:
        if self.index < 0:
            raise ValueError("swing index cannot be negative")
        _require_aware("swing time", self.time)
        _require_positive("swing price", self.price)
        if self.left_window < 1 or self.right_window < 1:
            raise ValueError("swing windows must be at least 1")


@dataclass(frozen=True, slots=True)
class TrendEvidence:
    higher_highs: int = 0
    higher_lows: int = 0
    lower_highs: int = 0
    lower_lows: int = 0
    equal_highs: int = 0
    equal_lows: int = 0
    persistence: float = 0.0
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "higher_highs",
            "higher_lows",
            "lower_highs",
            "lower_lows",
            "equal_highs",
            "equal_lows",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        _require_finite("trend persistence", self.persistence)
        if not 0 <= self.persistence <= 1:
            raise ValueError("trend persistence must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class TrendAnalysis:
    direction: TrendDirection
    strength: float
    evidence: TrendEvidence
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_finite("trend strength", self.strength)
        if not 0 <= self.strength <= 1:
            raise ValueError("trend strength must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class StructureBreak:
    direction: BreakDirection
    broken_swing: SwingPoint
    candle_index: int
    candle_time: datetime
    broken_level: float
    close_distance: float
    wick_penetration: float
    quality: BreakQuality
    confirmation: ConfirmationStatus
    evidence: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.candle_index <= self.broken_swing.index:
            raise ValueError("break candle must occur after the broken swing")
        _require_aware("break candle time", self.candle_time)
        _require_positive("broken level", self.broken_level)
        _require_finite("close distance", self.close_distance)
        _require_finite("wick penetration", self.wick_penetration)
        if self.wick_penetration < 0:
            raise ValueError("wick penetration cannot be negative")


@dataclass(frozen=True, slots=True)
class ChangeOfCharacter:
    prior_trend: TrendDirection
    break_event: StructureBreak
    confirmation: ConfirmationStatus
    evidence: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class StructureLevel:
    representative_price: float
    low: float
    high: float
    role: LevelRole
    status: LevelStatus
    touches: int
    pivot_indices: tuple[int, ...]
    last_touch_index: int

    def __post_init__(self) -> None:
        _require_positive("level representative price", self.representative_price)
        _require_positive("level low", self.low)
        _require_positive("level high", self.high)
        if self.low > self.high:
            raise ValueError("level low cannot exceed level high")
        if not self.low <= self.representative_price <= self.high:
            raise ValueError("representative price must lie inside the level")
        if self.touches < 1 or self.touches != len(self.pivot_indices):
            raise ValueError("touch count must match pivot indices")
        if tuple(sorted(set(self.pivot_indices))) != self.pivot_indices:
            raise ValueError("pivot indices must be unique and sorted")
        if self.last_touch_index != self.pivot_indices[-1]:
            raise ValueError("last touch index must match the final pivot index")


@dataclass(frozen=True, slots=True)
class RangeStructure:
    low: float
    high: float
    midpoint: float
    width: float
    width_percentage: float
    start_index: int
    end_index: int
    upper_tests: int
    lower_tests: int
    breakout_state: RangeBreakoutState
    current_position: float
    quality: float
    false_break_indices: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (
            ("range low", self.low),
            ("range high", self.high),
            ("range midpoint", self.midpoint),
        ):
            _require_positive(name, value)
        for name, value in (
            ("range width", self.width),
            ("range width percentage", self.width_percentage),
            ("current position", self.current_position),
            ("range quality", self.quality),
        ):
            _require_finite(name, value)
        if self.low >= self.high or self.width <= 0:
            raise ValueError("range must have positive width")
        if not math.isclose(self.width, self.high - self.low, rel_tol=1e-12, abs_tol=1e-12):
            raise ValueError("range width must equal high minus low")
        if not math.isclose(
            self.midpoint,
            (self.high + self.low) / 2,
            rel_tol=1e-12,
            abs_tol=1e-12,
        ):
            raise ValueError("range midpoint is inconsistent with boundaries")
        if self.start_index < 0 or self.end_index < self.start_index:
            raise ValueError("invalid range indices")
        if self.upper_tests < 0 or self.lower_tests < 0:
            raise ValueError("range test counts cannot be negative")
        if tuple(sorted(set(self.false_break_indices))) != self.false_break_indices:
            raise ValueError("false-break indices must be unique and sorted")
        if any(
            index < self.start_index or index > self.end_index for index in self.false_break_indices
        ):
            raise ValueError("false-break indices must lie inside the range interval")
        if not 0 <= self.current_position <= 1:
            raise ValueError("current position must be between 0 and 1")
        if not 0 <= self.quality <= 1:
            raise ValueError("range quality must be between 0 and 1")


@dataclass(frozen=True, slots=True)
class StructureEvidenceSummary:
    """Compact explainable snapshot of the detected structure state."""

    swing_count: int
    confirmed_swing_count: int
    developing_swing_count: int
    break_count: int
    actionable_break_count: int
    change_of_character_count: int
    range_count: int
    level_count: int
    latest_break_quality: BreakQuality | None = None
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name in (
            "swing_count",
            "confirmed_swing_count",
            "developing_swing_count",
            "break_count",
            "actionable_break_count",
            "change_of_character_count",
            "range_count",
            "level_count",
        ):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} cannot be negative")
        if self.confirmed_swing_count + self.developing_swing_count != self.swing_count:
            raise ValueError("swing status counts must equal total swing count")
        if self.actionable_break_count > self.break_count:
            raise ValueError("actionable break count cannot exceed total break count")


@dataclass(frozen=True, slots=True)
class StructureAnalysisResult:
    swings: tuple[SwingPoint, ...]
    trend: TrendAnalysis
    breaks: tuple[StructureBreak, ...] = ()
    changes_of_character: tuple[ChangeOfCharacter, ...] = ()
    ranges: tuple[RangeStructure, ...] = ()
    levels: tuple[StructureLevel, ...] = ()
    evidence_summary: StructureEvidenceSummary | None = None

    def __post_init__(self) -> None:
        if (
            tuple(sorted(self.swings, key=lambda item: (item.index, item.kind.value)))
            != self.swings
        ):
            raise ValueError("swings must use deterministic chronological ordering")
        if (
            tuple(sorted(self.breaks, key=lambda item: (item.candle_index, item.direction.value)))
            != self.breaks
        ):
            raise ValueError("breaks must use deterministic chronological ordering")
        if (
            tuple(sorted(self.ranges, key=lambda item: (item.start_index, item.end_index)))
            != self.ranges
        ):
            raise ValueError("ranges must use chronological ordering")
        if (
            tuple(
                sorted(
                    self.levels,
                    key=lambda item: (
                        item.representative_price,
                        item.role.value,
                        item.last_touch_index,
                    ),
                )
            )
            != self.levels
        ):
            raise ValueError("levels must use deterministic ordering")
        if self.evidence_summary is None:
            object.__setattr__(self, "evidence_summary", _summarize_structure(self))


def _summarize_structure(result: StructureAnalysisResult) -> StructureEvidenceSummary:
    confirmed_swings = sum(1 for item in result.swings if item.status is PivotStatus.CONFIRMED)
    developing_swings = sum(1 for item in result.swings if item.status is PivotStatus.DEVELOPING)
    actionable_breaks = tuple(
        item
        for item in result.breaks
        if item.confirmation is ConfirmationStatus.CONFIRMED
        and item.quality in {BreakQuality.VALID, BreakQuality.STRONG}
    )
    notes: list[str] = [
        f"trend={result.trend.direction.value}",
        f"trend_strength={result.trend.strength:.3f}",
    ]
    if result.ranges:
        latest_range = result.ranges[-1]
        notes.append(
            "range="
            f"{latest_range.low:.8g}-{latest_range.high:.8g};"
            f"quality={latest_range.quality:.3f}"
        )
    if result.changes_of_character:
        notes.append("change_of_character_present")
    return StructureEvidenceSummary(
        swing_count=len(result.swings),
        confirmed_swing_count=confirmed_swings,
        developing_swing_count=developing_swings,
        break_count=len(result.breaks),
        actionable_break_count=len(actionable_breaks),
        change_of_character_count=len(result.changes_of_character),
        range_count=len(result.ranges),
        level_count=len(result.levels),
        latest_break_quality=result.breaks[-1].quality if result.breaks else None,
        notes=tuple(notes),
    )
