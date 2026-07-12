"""Deterministic volume features for normalized candle sequences."""

from __future__ import annotations

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
class VolumePressureResult:
    """Aligned bullish and bearish volume-pressure foundations."""

    bullish: FeatureResult
    bearish: FeatureResult


def average_volume(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return aligned rolling average volume."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    volumes = finite_values([candle.volume for candle in prepared], name="candle volumes")
    return FeatureResult(
        spec=_series_spec(f"average_volume_{period}", period, active_candle_policy),
        values=rolling_mean(volumes, period),
    )


def relative_volume(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return volume divided by its rolling average."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    volumes = finite_values([candle.volume for candle in prepared], name="candle volumes")
    averages = rolling_mean(volumes, period)
    values = tuple(
        None if average is None else 0.0 if average == 0 else volume / average
        for volume, average in zip(volumes, averages, strict=True)
    )
    return FeatureResult(
        spec=_series_spec(f"relative_volume_{period}", period, active_candle_policy),
        values=values,
    )


def volume_spike(
    candles: Sequence[Candle],
    period: int = 20,
    threshold: float = 1.5,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return ``1.0`` when relative volume reaches the configured threshold."""

    if threshold <= 0:
        raise ValueError("threshold must be greater than zero")
    relative = relative_volume(
        candles,
        period,
        active_candle_policy=active_candle_policy,
    )
    values = tuple(
        None if value is None else 1.0 if value >= threshold else 0.0
        for value in relative.values
    )
    return FeatureResult(
        spec=_series_spec(f"volume_spike_{period}", period, active_candle_policy),
        values=values,
    )


def volume_pressure(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> VolumePressureResult:
    """Return rolling bullish and bearish volume shares.

    Doji volume is split evenly so both shares remain deterministic and bounded.
    """

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    bullish_raw: list[float] = []
    bearish_raw: list[float] = []
    for candle in prepared:
        if candle.close > candle.open:
            bullish_raw.append(candle.volume)
            bearish_raw.append(0.0)
        elif candle.close < candle.open:
            bullish_raw.append(0.0)
            bearish_raw.append(candle.volume)
        else:
            bullish_raw.append(candle.volume / 2.0)
            bearish_raw.append(candle.volume / 2.0)

    total_average = rolling_mean(
        [bullish + bearish for bullish, bearish in zip(bullish_raw, bearish_raw, strict=True)],
        period,
    )
    bullish_average = rolling_mean(bullish_raw, period)
    bearish_average = rolling_mean(bearish_raw, period)

    def shares(values: tuple[float | None, ...]) -> tuple[float | None, ...]:
        return tuple(
            None if value is None or total is None else 0.0 if total == 0 else value / total
            for value, total in zip(values, total_average, strict=True)
        )

    return VolumePressureResult(
        bullish=FeatureResult(
            spec=_series_spec(f"bullish_volume_pressure_{period}", period, active_candle_policy),
            values=shares(bullish_average),
        ),
        bearish=FeatureResult(
            spec=_series_spec(f"bearish_volume_pressure_{period}", period, active_candle_policy),
            values=shares(bearish_average),
        ),
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
