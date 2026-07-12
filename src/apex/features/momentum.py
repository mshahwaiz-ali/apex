"""Deterministic momentum features for normalized candle sequences."""

from __future__ import annotations

import itertools
from collections.abc import Sequence
from dataclasses import dataclass

from apex.domain.models import Candle
from apex.features.contracts import (
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    MissingDataPolicy,
)
from apex.features.numerical import finite_values, validate_period
from apex.features.validation import ActiveCandlePolicy, prepare_candles


@dataclass(frozen=True, slots=True)
class MacdResult:
    """Aligned MACD line, signal line, and histogram."""

    macd: FeatureResult
    signal: FeatureResult
    histogram: FeatureResult


def relative_strength_index(
    candles: Sequence[Candle],
    period: int = 14,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return Wilder RSI with ``None`` warm-up values.

    The first RSI appears at index ``period`` because ``period`` price changes
    require ``period + 1`` closes. Flat periods resolve to RSI 50, all-gain
    periods to 100, and all-loss periods to 0.
    """

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period + 1,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")
    changes = tuple(current - previous for previous, current in itertools.pairwise(closes))
    gains = tuple(max(change, 0.0) for change in changes)
    losses = tuple(max(-change, 0.0) for change in changes)

    average_gain = sum(gains[:period]) / period
    average_loss = sum(losses[:period]) / period
    output: list[float | None] = [None] * period
    output.append(_rsi_value(average_gain, average_loss))

    for gain, loss in zip(gains[period:], losses[period:], strict=True):
        average_gain = ((average_gain * (period - 1)) + gain) / period
        average_loss = ((average_loss * (period - 1)) + loss) / period
        output.append(_rsi_value(average_gain, average_loss))

    return FeatureResult(
        spec=_series_spec(f"rsi_{period}", period + 1, active_candle_policy),
        values=tuple(output),
    )


def rsi_slope(
    candles: Sequence[Candle],
    period: int = 14,
    lookback: int = 3,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return per-candle RSI change across ``lookback`` observations."""

    validate_period(lookback)
    prepared = prepare_candles(
        candles,
        minimum_candles=period + lookback + 1,
        active_candle_policy=active_candle_policy,
    )
    rsi = relative_strength_index(
        prepared,
        period,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    ).values
    output: list[float | None] = []
    for index, current in enumerate(rsi):
        previous_index = index - lookback
        previous = rsi[previous_index] if previous_index >= 0 else None
        if current is None or previous is None:
            output.append(None)
        else:
            output.append((current - previous) / lookback)
    return FeatureResult(
        spec=_series_spec(
            f"rsi_slope_{period}_{lookback}",
            period + lookback + 1,
            active_candle_policy,
        ),
        values=tuple(output),
    )


def rate_of_change(
    candles: Sequence[Candle],
    period: int = 12,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> FeatureResult:
    """Return percentage close-price change from ``period`` candles earlier."""

    validate_period(period)
    prepared = prepare_candles(
        candles,
        minimum_candles=period + 1,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")
    output: list[float | None] = [None] * period
    for index in range(period, len(closes)):
        previous = closes[index - period]
        output.append(((closes[index] - previous) / previous) * 100.0)
    return FeatureResult(
        spec=_series_spec(f"roc_{period}", period + 1, active_candle_policy),
        values=tuple(output),
    )


def macd(
    candles: Sequence[Candle],
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    *,
    active_candle_policy: ActiveCandlePolicy = ActiveCandlePolicy.DROP_FINAL,
) -> MacdResult:
    """Return SMA-seeded MACD, signal, and histogram series."""

    for period in (fast_period, slow_period, signal_period):
        validate_period(period)
    if fast_period >= slow_period:
        raise ValueError("fast_period must be lower than slow_period")

    minimum = slow_period + signal_period - 1
    prepared = prepare_candles(
        candles,
        minimum_candles=minimum,
        active_candle_policy=active_candle_policy,
    )
    closes = finite_values([candle.close for candle in prepared], name="candle closes")
    fast = _ema_values(closes, fast_period)
    slow = _ema_values(closes, slow_period)
    macd_values = tuple(
        None if fast_value is None or slow_value is None else fast_value - slow_value
        for fast_value, slow_value in zip(fast, slow, strict=True)
    )

    available_macd = tuple(value for value in macd_values if value is not None)
    signal_compact = _ema_values(available_macd, signal_period)
    leading = len(macd_values) - len(available_macd)
    signal_values = (None,) * leading + signal_compact
    histogram_values = tuple(
        None if line is None or signal is None else line - signal
        for line, signal in zip(macd_values, signal_values, strict=True)
    )

    return MacdResult(
        macd=FeatureResult(
            spec=_series_spec(
                f"macd_{fast_period}_{slow_period}", slow_period, active_candle_policy
            ),
            values=macd_values,
        ),
        signal=FeatureResult(
            spec=_series_spec(
                f"macd_signal_{fast_period}_{slow_period}_{signal_period}",
                minimum,
                active_candle_policy,
            ),
            values=signal_values,
        ),
        histogram=FeatureResult(
            spec=_series_spec(
                f"macd_histogram_{fast_period}_{slow_period}_{signal_period}",
                minimum,
                active_candle_policy,
            ),
            values=histogram_values,
        ),
    )


def _rsi_value(average_gain: float, average_loss: float) -> float:
    if average_gain == 0 and average_loss == 0:
        return 50.0
    if average_loss == 0:
        return 100.0
    if average_gain == 0:
        return 0.0
    relative_strength = average_gain / average_loss
    return 100.0 - (100.0 / (1.0 + relative_strength))


def _ema_values(values: Sequence[float], period: int) -> tuple[float | None, ...]:
    if len(values) < period:
        raise ValueError(f"period {period} exceeds available values {len(values)}")
    seed = sum(values[:period]) / period
    multiplier = 2.0 / (period + 1.0)
    output: list[float | None] = [None] * (period - 1)
    output.append(seed)
    previous = seed
    for value in values[period:]:
        previous = ((value - previous) * multiplier) + previous
        output.append(previous)
    return tuple(output)


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
