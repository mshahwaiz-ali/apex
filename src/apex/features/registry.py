"""Typed composition boundary for deterministic feature calculations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.momentum import macd, rate_of_change, relative_strength_index, rsi_slope
from apex.features.moving_averages import exponential_moving_average, simple_moving_average
from apex.features.price_location import (
    bollinger_position,
    distance_from_recent_extremes,
    recent_range_position,
    vwap,
)
from apex.features.trend import (
    ema_relationship,
    ema_slope,
    price_distance_from_ema,
    trend_persistence,
)
from apex.features.volatility import (
    atr_percentage,
    average_true_range,
    bollinger_bands,
    candle_range_ratio,
    true_range,
    wick_statistics,
)
from apex.features.volume import average_volume, relative_volume, volume_pressure, volume_spike

FeatureCalculator = Callable[[Sequence[Candle]], tuple[FeatureResult, ...]]


@dataclass(frozen=True, slots=True)
class IndicatorPeriods:
    """Dependency-neutral feature periods supplied by application configuration."""

    ema_fast: int = 20
    ema_slow: int = 50
    rsi: int = 14
    rsi_slope: int = 3
    roc: int = 12
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    atr: int = 14
    relative_volume: int = 20
    range_lookback: int = 20


@dataclass(frozen=True, slots=True)
class FeatureAuditEntry:
    """Inspectable runtime contract metadata for one calculated feature result."""

    group_name: str
    feature_name: str
    minimum_candles: int
    accepts_active_candle: bool
    output_shape: FeatureOutputShape
    missing_data_policy: MissingDataPolicy
    output_length: int
    finite_values: int
    missing_values: int

    def __post_init__(self) -> None:
        if not self.group_name.strip() or not self.feature_name.strip():
            raise ValueError("feature audit names cannot be empty")
        if self.minimum_candles < 1:
            raise ValueError("feature audit minimum candles must be at least one")
        if self.output_length < 1:
            raise ValueError("feature audit output length must be at least one")
        if self.finite_values < 0 or self.missing_values < 0:
            raise ValueError("feature audit counts cannot be negative")
        if self.finite_values + self.missing_values != self.output_length:
            raise ValueError("feature audit counts must equal output length")


@dataclass(slots=True)
class FeatureRegistry:
    """Register named deterministic calculations and evaluate them in order."""

    _calculators: dict[str, FeatureCalculator] = field(default_factory=dict)

    def register(self, name: str, calculator: FeatureCalculator) -> None:
        normalized = name.strip()
        if not normalized:
            raise ValueError("feature registry name cannot be empty")
        if normalized in self._calculators:
            raise ValueError(f"feature already registered: {normalized}")
        self._calculators[normalized] = calculator

    @property
    def names(self) -> tuple[str, ...]:
        """Return deterministic registration order."""

        return tuple(self._calculators)

    def calculate(self, name: str, candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
        """Evaluate one registered feature group."""

        try:
            calculator = self._calculators[name]
        except KeyError as exc:
            raise ValueError(f"unknown feature: {name}") from exc
        return calculator(candles)

    def calculate_all(self, candles: Sequence[Candle]) -> dict[str, tuple[FeatureResult, ...]]:
        """Evaluate all groups in deterministic registration order."""

        return {name: calculator(candles) for name, calculator in self._calculators.items()}

    def audit(self, candles: Sequence[Candle]) -> tuple[FeatureAuditEntry, ...]:
        """Return deterministic feature contract metadata from one evaluation pass."""

        entries: list[FeatureAuditEntry] = []
        for group_name, results in self.calculate_all(candles).items():
            for result in results:
                finite_count = sum(value is not None for value in result.values)
                missing_count = len(result.values) - finite_count
                entries.append(
                    FeatureAuditEntry(
                        group_name=group_name,
                        feature_name=result.spec.name,
                        minimum_candles=result.spec.minimum_candles,
                        accepts_active_candle=result.spec.accepts_active_candle,
                        output_shape=result.spec.output_shape,
                        missing_data_policy=result.spec.missing_data_policy,
                        output_length=len(result.values),
                        finite_values=finite_count,
                        missing_values=missing_count,
                    )
                )
        return tuple(entries)


def create_default_feature_registry(
    profile: IndicatorPeriods | None = None,
) -> FeatureRegistry:
    """Return the complete deterministic feature composition."""

    periods = profile or IndicatorPeriods()
    registry = FeatureRegistry()
    registry.register("sma_20", lambda candles: (simple_moving_average(candles, 20),))
    registry.register(
        "ema_20", lambda candles: (exponential_moving_average(candles, periods.ema_fast),)
    )
    registry.register(
        "ema_50", lambda candles: (exponential_moving_average(candles, periods.ema_slow),)
    )
    registry.register("ema_200", lambda candles: (exponential_moving_average(candles, 200),))
    registry.register("rsi_14", lambda candles: (relative_strength_index(candles, periods.rsi),))
    registry.register(
        "rsi_slope_14_3",
        lambda candles: (rsi_slope(candles, periods.rsi, periods.rsi_slope),),
    )
    registry.register("roc_12", lambda candles: (rate_of_change(candles, periods.roc),))
    registry.register(
        "macd",
        lambda candles: _macd_results(
            candles,
            fast=periods.macd_fast,
            slow=periods.macd_slow,
            signal=periods.macd_signal,
        ),
    )
    registry.register("true_range", lambda candles: (true_range(candles),))
    registry.register("atr_14", lambda candles: (average_true_range(candles, periods.atr),))
    registry.register("atr_percentage_14", lambda candles: (atr_percentage(candles, periods.atr),))
    registry.register("bollinger_20", _bollinger_results)
    registry.register(
        "candle_range_ratio_20",
        lambda candles: (candle_range_ratio(candles, periods.range_lookback),),
    )
    registry.register("wick_statistics_latest", _wick_statistics_result)
    registry.register(
        "average_volume_20", lambda candles: (average_volume(candles, periods.relative_volume),)
    )
    registry.register(
        "relative_volume_20", lambda candles: (relative_volume(candles, periods.relative_volume),)
    )
    registry.register(
        "volume_spike_20_1_5",
        lambda candles: (volume_spike(candles, periods.relative_volume, 1.5),),
    )
    registry.register("volume_pressure_20", _volume_pressure_results)
    registry.register("vwap", lambda candles: (vwap(candles),))
    registry.register(
        "recent_range_position_20",
        lambda candles: (recent_range_position(candles, periods.range_lookback),),
    )
    registry.register(
        "bollinger_position_20_2", lambda candles: (bollinger_position(candles, 20, 2.0),)
    )
    registry.register(
        "distance_from_recent_extremes_20",
        lambda candles: distance_from_recent_extremes(candles, periods.range_lookback),
    )
    registry.register("ema_relationship_12_26", _ema_relationship_results)
    registry.register("ema_slope_20_3", lambda candles: (ema_slope(candles, 20, 3),))
    registry.register(
        "price_distance_from_ema_20",
        lambda candles: (price_distance_from_ema(candles, 20),),
    )
    registry.register(
        "trend_persistence_20_10", lambda candles: (trend_persistence(candles, 20, 10),)
    )
    return registry


def _macd_results(
    candles: Sequence[Candle], *, fast: int = 12, slow: int = 26, signal: int = 9
) -> tuple[FeatureResult, ...]:
    result = macd(candles, fast_period=fast, slow_period=slow, signal_period=signal)
    return result.macd, result.signal, result.histogram


def _bollinger_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = bollinger_bands(candles)
    return result.middle, result.upper, result.lower, result.width


def _ema_relationship_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = ema_relationship(candles)
    return result.spread_percentage, result.direction, result.strength


def _volume_pressure_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = volume_pressure(candles)
    return result.bullish, result.bearish


def _recent_extreme_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    return distance_from_recent_extremes(candles, 20)


def _wick_statistics_result(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    if not candles:
        raise ValueError("at least 1 candle is required; received 0")
    candle = candles[-2] if not candles[-1].is_closed and len(candles) > 1 else candles[-1]
    if not candle.is_closed:
        raise ValueError("at least 1 closed candle is required")
    statistics = wick_statistics(candle)
    specs = (
        FeatureSpec(
            "latest_upper_wick_ratio", 1, False, FeatureOutputShape.SCALAR, MissingDataPolicy.NONE
        ),
        FeatureSpec(
            "latest_lower_wick_ratio", 1, False, FeatureOutputShape.SCALAR, MissingDataPolicy.NONE
        ),
        FeatureSpec(
            "latest_body_ratio", 1, False, FeatureOutputShape.SCALAR, MissingDataPolicy.NONE
        ),
    )
    return (
        FeatureResult(specs[0], (statistics.upper_ratio,)),
        FeatureResult(specs[1], (statistics.lower_ratio,)),
        FeatureResult(specs[2], (statistics.body_ratio,)),
    )
