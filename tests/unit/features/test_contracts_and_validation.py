from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.features import (
    ActiveCandlePolicy,
    FeatureOutputShape,
    FeatureResult,
    FeatureSpec,
    prepare_candles,
)


def make_candle(index: int, *, is_closed: bool = True) -> Candle:
    open_time = datetime(2026, 7, 12, 10, 0, tzinfo=UTC) + timedelta(minutes=15 * index)
    return Candle(
        symbol="BTC/USDT",
        timeframe="15m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=15),
        open=100.0 + index,
        high=101.0 + index,
        low=99.0 + index,
        close=100.5 + index,
        volume=10.0 + index,
        is_closed=is_closed,
        source="binance",
    )


def test_feature_spec_rejects_invalid_contracts() -> None:
    with pytest.raises(ValueError, match="name cannot be empty"):
        FeatureSpec(
            name=" ",
            minimum_candles=1,
            accepts_active_candle=False,
            output_shape=FeatureOutputShape.SCALAR,
        )

    with pytest.raises(ValueError, match="at least 1"):
        FeatureSpec(
            name="sma",
            minimum_candles=0,
            accepts_active_candle=False,
            output_shape=FeatureOutputShape.SCALAR,
        )


def test_feature_result_rejects_non_finite_values() -> None:
    spec = FeatureSpec(
        name="sma",
        minimum_candles=3,
        accepts_active_candle=False,
        output_shape=FeatureOutputShape.SCALAR,
    )

    with pytest.raises(ValueError, match="NaN or infinite"):
        FeatureResult(spec=spec, values=(float("nan"),))


def test_default_policy_drops_final_active_candle() -> None:
    candles = [make_candle(0), make_candle(1), make_candle(2, is_closed=False)]

    prepared = prepare_candles(candles, minimum_candles=2)

    assert prepared == tuple(candles[:2])


def test_allow_policy_keeps_final_active_candle() -> None:
    candles = [make_candle(0), make_candle(1, is_closed=False)]

    prepared = prepare_candles(
        candles,
        minimum_candles=2,
        active_candle_policy=ActiveCandlePolicy.ALLOW_FINAL,
    )

    assert prepared == tuple(candles)


def test_reject_policy_rejects_active_candle() -> None:
    candles = [make_candle(0), make_candle(1, is_closed=False)]

    with pytest.raises(ValueError, match="not accepted"):
        prepare_candles(
            candles,
            minimum_candles=1,
            active_candle_policy=ActiveCandlePolicy.REJECT,
        )


def test_validation_rejects_mixed_or_unordered_series() -> None:
    first = make_candle(0)
    second = make_candle(1).model_copy(update={"symbol": "ETH/USDT"})

    with pytest.raises(ValueError, match="symbol"):
        prepare_candles([first, second], minimum_candles=1)

    with pytest.raises(ValueError, match="ordered"):
        prepare_candles([make_candle(1), make_candle(0)], minimum_candles=1)


def test_minimum_length_is_checked_after_active_candle_removal() -> None:
    candles = [make_candle(0), make_candle(1, is_closed=False)]

    with pytest.raises(ValueError, match="received 1"):
        prepare_candles(candles, minimum_candles=2)
