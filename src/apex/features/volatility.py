"""Deterministic volatility and candle-shape features."""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.numerical import finite_values, rolling_mean, validate_period
from apex.features.validation import ActiveCandlePolicy, prepare_candles


@dataclass(frozen=True, slots=True)
class BollingerBandsResult:
    """Aligned Bollinger Band components."""

    middle: FeatureResult
    upper: FeatureResult
    lower: FeatureResult
    width: FeatureResult


@dataclass(frozen=True, slots=True)
class WickStatistics:
    """Latest candle wick proportions relative to total range."""

    upper_ratio: float
    lower_ratio: float
    body_ratio: float

    def __post_init__(self) -> None:
        for value in (self.upper_ratio, self.lower_ratio, self.body_ratio):
            if not math.isfinite(value) or value < 0 or value > 1:
                raise ValueError("wick ratios must be finite values between 0 and 1")


def true_range(
    candles: Sequence[Candle],
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return aligned true range values.

    The first value uses ``high - low`` because no previous close is available.
    """

    prepared = prepare_candles(
        candles,
        minimum_candles=1,
        active_candle_policy=active_candle_policy,
    )
    values: list[float] = []
    for index, candle in enumerate(prepared):
        if index == 0:
            values.append(candle.high - candle.low)
            continue
        previous_close = prepared[index - 1].close
        values.append(
            max(
                candle.high - candle.low,
                abs(candle.high - previous_close),
                abs(candle.low - previous_close),
            )
        )
    spec = _series_spec("true_range", 1, active_candle_policy)
    return FeatureResult(spec=spec, values=tuple(values))


def average_true_range(
    candles: Sequence[Candle],
    period: int = 14,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return Wilder-smoothed ATR seeded by the first true-range average."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    ranges = true_range(
        prepared,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    numeric_ranges = finite_values(
        [value for value in ranges if value is not None],
        name="true ranges",
    )
    seed = sum(numeric_ranges[:period]) / period
    output: list[float | None] = [None] * (period - 1)
    output.append(seed)
    previous = seed
    for current in numeric_ranges[period:]:
        previous = ((previous * (period - 1)) + current) / period
        output.append(previous)
    return FeatureResult(
        spec=_series_spec(f"atr_{period}", period, active_candle_policy),
        values=tuple(output),
    )


def atr_percentage(
    candles: Sequence[Candle],
    period: int = 14,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return ATR as a percentage of close price."""

    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    atr = average_true_range(
        prepared,
        period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )
    values = tuple(
        None if value is None else (value / candle.close) * 100.0
        for candle, value in zip(prepared, atr.values, strict=True)
    )
    return FeatureResult(
        spec=_series_spec(f"atr_percentage_{period}", period, active_candle_policy),
        values=values,
    )


def bollinger_bands(
    candles: Sequence[Candle],
    period: int = 20,
    standard_deviations: float = 2.0,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> BollingerBandsResult:
    """Return population-standard-deviation Bollinger Bands and width percent."""

    validate_period(period)
    if not math.isfinite(standard_deviations) or standard_deviations <= 0:
        raise ValueError("standard_deviations must be a positive finite value")
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")
    middle_values = rolling_mean(closes, period)
    upper: list[float | None] = [None] * (period - 1)
    lower: list[float | None] = [None] * (period - 1)
    width: list[float | None] = [None] * (period - 1)
    for index in range(period - 1, len(closes)):
        window = closes[index - period + 1 : index + 1]
        mean = sum(window) / period
        variance = sum((value - mean) ** 2 for value in window) / period
        deviation = math.sqrt(variance) * standard_deviations
        upper_value = mean + deviation
        lower_value = mean - deviation
        upper.append(upper_value)
        lower.append(lower_value)
        width.append(((upper_value - lower_value) / mean) * 100.0)
    return BollingerBandsResult(
        middle=FeatureResult(
            spec=_series_spec(f"bollinger_middle_{period}", period, active_candle_policy),
            values=middle_values,
        ),
        upper=FeatureResult(
            spec=_series_spec(f"bollinger_upper_{period}", period, active_candle_policy),
            values=tuple(upper),
        ),
        lower=FeatureResult(
            spec=_series_spec(f"bollinger_lower_{period}", period, active_candle_policy),
            values=tuple(lower),
        ),
        width=FeatureResult(
            spec=_series_spec(f"bollinger_width_{period}", period, active_candle_policy),
            values=tuple(width),
        ),
    )


def candle_range_ratio(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return candle range divided by its rolling average range."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    ranges = finite_values(
        [candle.high - candle.low for candle in prepared],
        name="candle ranges",
    )
    averages = rolling_mean(ranges, period)
    values = tuple(
        None if average is None or average == 0 else current / average
        for current, average in zip(ranges, averages, strict=True)
    )
    return FeatureResult(
        spec=_series_spec(f"candle_range_ratio_{period}", period, active_candle_policy),
        values=values,
    )


def wick_statistics(candle: Candle) -> WickStatistics:
    """Return deterministic upper-wick, lower-wick, and body proportions."""

    total_range = candle.high - candle.low
    if total_range == 0:
        return WickStatistics(upper_ratio=0.0, lower_ratio=0.0, body_ratio=0.0)
    body_high = max(candle.open, candle.close)
    body_low = min(candle.open, candle.close)
    return WickStatistics(
        upper_ratio=(candle.high - body_high) / total_range,
        lower_ratio=(body_low - candle.low) / total_range,
        body_ratio=abs(candle.close - candle.open) / total_range,
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
