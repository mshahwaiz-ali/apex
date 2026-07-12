"""Typed composition boundary for deterministic feature calculations."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from apex.domain.models import Candle
from apex.features.contracts import FeatureResult
from apex.features.momentum import macd, rate_of_change, relative_strength_index
from apex.features.moving_averages import exponential_moving_average, simple_moving_average
from apex.features.price_location import recent_range_position, vwap
from apex.features.trend import ema_relationship, ema_slope, price_distance_from_ema
from apex.features.volatility import average_true_range, bollinger_bands
from apex.features.volume import average_volume, relative_volume

FeatureCalculator = Callable[[Sequence[Candle]], tuple[FeatureResult, ...]]


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


def create_default_feature_registry() -> FeatureRegistry:
    """Return the initial production feature composition without strategy logic."""

    registry = FeatureRegistry()
    registry.register("sma_20", lambda candles: (simple_moving_average(candles, 20),))
    registry.register("ema_20", lambda candles: (exponential_moving_average(candles, 20),))
    registry.register("atr_14", lambda candles: (average_true_range(candles, 14),))
    registry.register("rsi_14", lambda candles: (relative_strength_index(candles, 14),))
    registry.register("roc_12", lambda candles: (rate_of_change(candles, 12),))
    registry.register("macd", _macd_results)
    registry.register("bollinger_20", _bollinger_results)
    registry.register("average_volume_20", lambda candles: (average_volume(candles, 20),))
    registry.register("relative_volume_20", lambda candles: (relative_volume(candles, 20),))
    registry.register("vwap", lambda candles: (vwap(candles),))
    registry.register(
        "recent_range_position_20",
        lambda candles: (recent_range_position(candles, 20),),
    )
    registry.register("ema_relationship", _ema_relationship_results)
    registry.register("ema_slope_20", lambda candles: (ema_slope(candles, 20, 3),))
    registry.register(
        "price_distance_from_ema_20",
        lambda candles: (price_distance_from_ema(candles, 20),),
    )
    return registry


def _macd_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = macd(candles)
    return result.macd, result.signal, result.histogram


def _bollinger_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = bollinger_bands(candles)
    return result.middle, result.upper, result.lower, result.width


def _ema_relationship_results(candles: Sequence[Candle]) -> tuple[FeatureResult, ...]:
    result = ema_relationship(candles)
    return result.spread_percentage, result.direction, result.strength
