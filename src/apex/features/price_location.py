"""Deterministic price-location features."""

from __future__ import annotations

from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.validation import ActiveCandlePolicy, prepare_candles
from apex.features.volatility import bollinger_bands


def recent_range_position(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return close position inside the recent high-low range, bounded to 0..1."""

    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    output: list[float | None] = [None] * (period - 1)
    for index in range(period - 1, len(prepared)):
        window = prepared[index - period + 1 : index + 1]
        highest = max(candle.high for candle in window)
        lowest = min(candle.low for candle in window)
        span = highest - lowest
        value = 0.5 if span == 0 else (prepared[index].close - lowest) / span
        output.append(min(1.0, max(0.0, value)))
    return FeatureResult(
        spec=_series_spec(f"recent_range_position_{period}", period, active_candle_policy),
        values=tuple(output),
    )


def distance_from_recent_extremes(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> tuple[FeatureResult, FeatureResult]:
    """Return percentage distance below recent high and above recent low."""

    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    high_distance: list[float | None] = [None] * (period - 1)
    low_distance: list[float | None] = [None] * (period - 1)
    for index in range(period - 1, len(prepared)):
        window = prepared[index - period + 1 : index + 1]
        highest = max(candle.high for candle in window)
        lowest = min(candle.low for candle in window)
        close = prepared[index].close
        high_distance.append(((highest - close) / close) * 100.0)
        low_distance.append(((close - lowest) / close) * 100.0)
    return (
        FeatureResult(
            spec=_series_spec(f"distance_from_recent_high_{period}", period, active_candle_policy),
            values=tuple(high_distance),
        ),
        FeatureResult(
            spec=_series_spec(f"distance_from_recent_low_{period}", period, active_candle_policy),
            values=tuple(low_distance),
        ),
    )


def vwap(
    candles: Sequence[Candle],
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return cumulative typical-price VWAP.

    When cumulative volume is zero, the current typical price is used to avoid
    NaN or infinite output.
    """

    prepared = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    cumulative_value = 0.0
    cumulative_volume = 0.0
    output: list[float] = []
    for candle in prepared:
        typical = (candle.high + candle.low + candle.close) / 3.0
        cumulative_value += typical * candle.volume
        cumulative_volume += candle.volume
        output.append(typical if cumulative_volume == 0 else cumulative_value / cumulative_volume)
    return FeatureResult(
        spec=_series_spec("vwap", 1, active_candle_policy),
        values=tuple(output),
    )


def bollinger_position(
    candles: Sequence[Candle],
    period: int = 20,
    standard_deviations: float = 2.0,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return close position between lower and upper Bollinger Bands."""

    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    bands = bollinger_bands(
        prepared,
        period,
        standard_deviations,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    output: list[float | None] = []
    for candle, lower, upper in zip(
        prepared,
        bands.lower.values,
        bands.upper.values,
        strict=True,
    ):
        if lower is None or upper is None:
            output.append(None)
            continue
        span = upper - lower
        output.append(0.5 if span == 0 else (candle.close - lower) / span)
    return FeatureResult(
        spec=_series_spec(f"bollinger_position_{period}", period, active_candle_policy),
        values=tuple(output),
    )


def _series_spec(
    name: str,
    minimum_candles: int,
    active_candle_policy: ActiveCandlePolicy,
) -> FeatureSpec:
    return FeatureSpec(
        name=name,
        minimum_candles=minimum_candles,
        accepts_active_candle=active_candle_policy is ActiveCandlePolicy.ALLOW_FINAL,
        output_shape=FeatureOutputShape.SERIES,
        missing_data_policy=MissingDataPolicy.NONE,
    )
