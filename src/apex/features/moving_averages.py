"""Deterministic close-price moving-average features."""

from __future__ import annotations

from collections.abc import Sequence

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.numerical import finite_values, rolling_mean, validate_period
from apex.features.validation import ActiveCandlePolicy, prepare_candles


def simple_moving_average(
    candles: Sequence[Candle],
    period: int,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return an aligned close-price SMA series.

    The first ``period - 1`` values are ``None``. By default, a final active
    candle is removed before calculation to prevent unstable live values.
    """

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")
    spec = _moving_average_spec("sma", period, active_candle_policy)
    return FeatureResult(spec=spec, values=rolling_mean(closes, period))


def exponential_moving_average(
    candles: Sequence[Candle],
    period: int,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return an aligned close-price EMA series seeded by the initial SMA.

    The smoothing multiplier is ``2 / (period + 1)``. Values before the seed
    are ``None`` and the seed at index ``period - 1`` is the SMA of the first
    complete period.
    """

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")

    seed = sum(closes[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    output: list[float | None] = [None] * (period - 1)
    output.append(seed)

    previous = seed
    for close in closes[period:]:
        previous = ((close - previous) * multiplier) + previous
        output.append(previous)

    spec = _moving_average_spec("ema", period, active_candle_policy)
    return FeatureResult(spec=spec, values=tuple(output))


def _moving_average_spec(
    kind: str,
    period: int,
    active_candle_policy: ActiveCandlePolicy,
) -> FeatureSpec:
    return FeatureSpec(
        name=f"{kind}_close_{period}",
        minimum_candles=period,
        accepts_active_candle=active_candle_policy is ActiveCandlePolicy.ALLOW_FINAL,
        output_shape=FeatureOutputShape.SERIES,
        missing_data_policy=MissingDataPolicy.NONE,
    )
