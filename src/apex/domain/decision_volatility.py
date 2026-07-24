"""Canonical decision-time, symbol-relative volatility profiling."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from apex.domain.models import Candle


class DecisionVolatilityClass(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class DecisionVolatilityProfile:
    volatility_class: DecisionVolatilityClass
    atr_pct: float | None
    realized_range_pct: float | None
    percentile: float | None
    source: str
    timeframe: str
    sample_size: int
    baseline_bars: int
    available: bool
    unavailable_reason: str | None = None
    authority: str = "observe_only"

    def __post_init__(self) -> None:
        if not self.source.strip() or not self.timeframe.strip():
            raise ValueError("decision volatility source and timeframe cannot be empty")
        if self.sample_size < 0 or self.baseline_bars < 0:
            raise ValueError("decision volatility counts cannot be negative")
        for value in (self.atr_pct, self.realized_range_pct, self.percentile):
            if value is not None and not math.isfinite(value):
                raise ValueError("decision volatility measurements must be finite")
        if self.percentile is not None and not 0.0 <= self.percentile <= 100.0:
            raise ValueError("decision volatility percentile must be between zero and 100")
        if self.available:
            if self.volatility_class is DecisionVolatilityClass.UNKNOWN:
                raise ValueError("available profile cannot be unknown")
            if None in (self.atr_pct, self.realized_range_pct, self.percentile):
                raise ValueError("available profile requires all measurements")
            if self.unavailable_reason is not None:
                raise ValueError("available profile cannot have an unavailable reason")
        elif self.volatility_class is not DecisionVolatilityClass.UNKNOWN:
            raise ValueError("unavailable profile must be unknown")
        elif not self.unavailable_reason:
            raise ValueError("unavailable profile requires a reason")

    def as_metadata(self) -> dict[str, str | int | float | bool | None]:
        return {
            "decision_volatility_class": self.volatility_class.value,
            "decision_volatility_atr_pct": self.atr_pct,
            "decision_realized_range_pct": self.realized_range_pct,
            "decision_volatility_percentile": self.percentile,
            "decision_volatility_source": self.source,
            "decision_volatility_timeframe": self.timeframe,
            "decision_volatility_sample_size": self.sample_size,
            "decision_volatility_baseline_bars": self.baseline_bars,
            "decision_volatility_available": self.available,
            "decision_volatility_unavailable_reason": self.unavailable_reason,
            "decision_volatility_authority": self.authority,
        }

    @classmethod
    def from_metadata(cls, metadata: Mapping[str, object]) -> DecisionVolatilityProfile | None:
        raw_class = metadata.get("decision_volatility_class")
        source = metadata.get("decision_volatility_source")
        timeframe = metadata.get("decision_volatility_timeframe")
        if not all(isinstance(item, str) for item in (raw_class, source, timeframe)):
            return None

        def number(key: str) -> float | None:
            value = metadata.get(key)
            if isinstance(value, bool) or not isinstance(value, int | float):
                return None
            result = float(value)
            return result if math.isfinite(result) else None

        def integer(key: str) -> int:
            value = metadata.get(key)
            return value if isinstance(value, int) and not isinstance(value, bool) else 0

        reason = metadata.get("decision_volatility_unavailable_reason")
        return cls(
            volatility_class=DecisionVolatilityClass(str(raw_class)),
            atr_pct=number("decision_volatility_atr_pct"),
            realized_range_pct=number("decision_realized_range_pct"),
            percentile=number("decision_volatility_percentile"),
            source=str(source),
            timeframe=str(timeframe),
            sample_size=integer("decision_volatility_sample_size"),
            baseline_bars=integer("decision_volatility_baseline_bars"),
            available=metadata.get("decision_volatility_available") is True,
            unavailable_reason=reason if isinstance(reason, str) else None,
        )


def _unavailable(
    timeframe: str, sample_size: int, baseline_bars: int, reason: str
) -> DecisionVolatilityProfile:
    return DecisionVolatilityProfile(
        volatility_class=DecisionVolatilityClass.UNKNOWN,
        atr_pct=None,
        realized_range_pct=None,
        percentile=None,
        source="unavailable",
        timeframe=timeframe,
        sample_size=sample_size,
        baseline_bars=baseline_bars,
        available=False,
        unavailable_reason=reason,
    )


def _percentile_rank(values: Sequence[float], current: float) -> float:
    below = sum(value < current for value in values)
    equal = sum(math.isclose(value, current, rel_tol=1e-12, abs_tol=1e-12) for value in values)
    return 100.0 * (below + 0.5 * equal) / len(values)


def _classify(percentile: float) -> DecisionVolatilityClass:
    if percentile < 20.0:
        return DecisionVolatilityClass.LOW
    if percentile < 75.0:
        return DecisionVolatilityClass.NORMAL
    if percentile < 95.0:
        return DecisionVolatilityClass.HIGH
    return DecisionVolatilityClass.EXTREME


def build_decision_volatility_profile(
    candles: Sequence[Candle],
    *,
    decision_time: datetime,
    atr_period: int = 14,
    baseline_bars: int = 120,
    minimum_observations: int = 20,
) -> DecisionVolatilityProfile:
    """Use only candles closed by decision_time; future replay candles are excluded."""

    closed = tuple(
        candle for candle in candles if candle.is_closed and candle.close_time <= decision_time
    )
    timeframe = closed[-1].timeframe if closed else "unknown"
    if len(closed) < atr_period + minimum_observations + 1:
        return _unavailable(
            timeframe,
            max(0, len(closed) - atr_period),
            baseline_bars,
            "insufficient_history",
        )

    true_ranges: list[float] = []
    observations: list[tuple[float, float]] = []
    for index in range(1, len(closed)):
        candle = closed[index]
        previous_close = closed[index - 1].close
        true_ranges.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
        if len(true_ranges) < atr_period:
            continue
        atr = sum(true_ranges[-atr_period:]) / atr_period
        atr_pct = atr / candle.close * 100.0
        range_pct = (candle.high - candle.low) / candle.close * 100.0
        if atr_pct > 0.0 and range_pct >= 0.0:
            observations.append((atr_pct, range_pct))

    if len(observations) < minimum_observations + 1:
        return _unavailable(
            timeframe,
            max(0, len(observations) - 1),
            baseline_bars,
            "insufficient_valid_observations",
        )

    current_atr_pct, current_range_pct = observations[-1]
    baseline = observations[max(0, len(observations) - baseline_bars - 1) : -1]
    if len(baseline) < minimum_observations:
        return _unavailable(timeframe, len(baseline), baseline_bars, "insufficient_baseline")

    atr_rank = _percentile_rank(tuple(item[0] for item in baseline), current_atr_pct)
    range_rank = _percentile_rank(tuple(item[1] for item in baseline), current_range_pct)
    percentile = 0.70 * atr_rank + 0.30 * range_rank
    return DecisionVolatilityProfile(
        volatility_class=_classify(percentile),
        atr_pct=current_atr_pct,
        realized_range_pct=current_range_pct,
        percentile=percentile,
        source=(
            "dynamic_symbol_profile"
            if len(baseline) >= 40
            else "dynamic_symbol_profile_limited_history"
        ),
        timeframe=timeframe,
        sample_size=len(baseline),
        baseline_bars=baseline_bars,
        available=True,
    )
