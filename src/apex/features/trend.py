"""Deterministic trend foundation features."""

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
from apex.features.moving_averages import exponential_moving_average
from apex.features.numerical import validate_period
from apex.features.validation import ActiveCandlePolicy, prepare_candles


@dataclass(frozen=True, slots=True)
class EmaRelationshipResult:
    """Aligned fast/slow EMA relationship foundations."""

    spread_percentage: FeatureResult
    direction: FeatureResult
    strength: FeatureResult


def ema_relationship(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> EmaRelationshipResult:
    """Return fast/slow EMA spread, direction, and absolute strength.

    Spread is normalized by close price and expressed as a percentage. Direction
    is ``1.0`` when the fast EMA is above the slow EMA, ``-1.0`` when below,
    and ``0.0`` when equal.
    """

    validate_period(fast_period)
    validate_period(slow_period)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be lower than slow_period")

    prepared = prepare_candles(
        candles,
        minimum_candles=slow_period,
        active_candle_policy=active_candle_policy,
    )
    fast = exponential_moving_average(
        prepared,
        fast_period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    slow = exponential_moving_average(
        prepared,
        slow_period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values

    spread_values: list[float | None] = []
    direction_values: list[float | None] = []
    strength_values: list[float | None] = []
    for candle, fast_value, slow_value in zip(prepared, fast, slow, strict=True):
        if fast_value is None or slow_value is None:
            spread_values.append(None)
            direction_values.append(None)
            strength_values.append(None)
            continue
        spread = ((fast_value - slow_value) / candle.close) * 100.0
        spread_values.append(spread)
        direction_values.append(1.0 if spread > 0 else -1.0 if spread < 0 else 0.0)
        strength_values.append(abs(spread))

    minimum = slow_period
    return EmaRelationshipResult(
        spread_percentage=FeatureResult(
            spec=_series_spec(
                f"ema_spread_percentage_{fast_period}_{slow_period}",
                minimum,
                active_candle_policy,
            ),
            values=tuple(spread_values),
        ),
        direction=FeatureResult(
            spec=_series_spec(
                f"ema_direction_{fast_period}_{slow_period}",
                minimum,
                active_candle_policy,
            ),
            values=tuple(direction_values),
        ),
        strength=FeatureResult(
            spec=_series_spec(
                f"ema_strength_{fast_period}_{slow_period}",
                minimum,
                active_candle_policy,
            ),
            values=tuple(strength_values),
        ),
    )


def ema_slope(
    candles: Sequence[Candle],
    period: int = 20,
    lookback: int = 3,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return EMA percentage change per candle across ``lookback`` observations."""

    validate_period(period)
    validate_period(lookback)
    prepared = prepare_candles(
        candles,
        minimum_candles=period + lookback,
        active_candle_policy=active_candle_policy,
    )
    ema = exponential_moving_average(
        prepared,
        period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    output: list[float | None] = []
    for index, current in enumerate(ema):
        previous_index = index - lookback
        previous = ema[previous_index] if previous_index >= 0 else None
        if current is None or previous is None:
            output.append(None)
        else:
            output.append(((current - previous) / previous) * 100.0 / lookback)
    return FeatureResult(
        spec=_series_spec(
            f"ema_slope_{period}_{lookback}",
            period + lookback,
            active_candle_policy,
        ),
        values=tuple(output),
    )


def price_distance_from_ema(
    candles: Sequence[Candle],
    period: int = 20,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return close-price distance from EMA as a signed percentage."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    ema = exponential_moving_average(
        prepared,
        period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    values = tuple(
        None if ema_value is None else ((candle.close - ema_value) / ema_value) * 100.0
        for candle, ema_value in zip(prepared, ema, strict=True)
    )
    return FeatureResult(
        spec=_series_spec(f"price_distance_from_ema_{period}", period, active_candle_policy),
        values=values,
    )


def trend_persistence(
    candles: Sequence[Candle],
    ema_period: int = 20,
    lookback: int = 10,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return rolling directional persistence of closes relative to EMA.

    Values range from ``-1`` to ``1``. A value of ``1`` means every close in
    the lookback window is above the EMA, while ``-1`` means every close is
    below it. Equality contributes zero.
    """

    validate_period(ema_period)
    validate_period(lookback)
    minimum = ema_period + lookback - 1
    prepared = prepare_candles(
        candles,
        minimum_candles=minimum,
        active_candle_policy=active_candle_policy,
    )
    ema = exponential_moving_average(
        prepared,
        ema_period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    states: list[float | None] = []
    for candle, ema_value in zip(prepared, ema, strict=True):
        if ema_value is None:
            states.append(None)
        elif candle.close > ema_value:
            states.append(1.0)
        elif candle.close < ema_value:
            states.append(-1.0)
        else:
            states.append(0.0)

    output: list[float | None] = []
    for index in range(len(states)):
        if index < lookback - 1:
            output.append(None)
            continue
        window = states[index - lookback + 1 : index + 1]
        if any(value is None for value in window):
            output.append(None)
        else:
            output.append(sum(value for value in window if value is not None) / lookback)

    return FeatureResult(
        spec=_series_spec(
            f"trend_persistence_{ema_period}_{lookback}",
            minimum,
            active_candle_policy,
        ),
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
