from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.strategies.context import FeatureSnapshot
from apex.strategies.continuation_freshness import (
    ContinuationState,
    measure_continuation_freshness,
)
from apex.strategies.contracts import TradeDirection

NOW = datetime(2026, 7, 21, tzinfo=UTC)


def _candles(*, bodies: tuple[float, float, float]) -> tuple[Candle, ...]:
    result: list[Candle] = []
    base = 100.0
    for index, body in enumerate(bodies):
        open_price = base
        close_price = open_price + body
        result.append(
            Candle(
                symbol="TESTUSDT",
                timeframe="5m",
                open_time=NOW + timedelta(minutes=index * 5),
                close_time=NOW + timedelta(minutes=(index + 1) * 5),
                open=open_price,
                high=max(open_price, close_price) + 0.2,
                low=min(open_price, close_price) - 0.2,
                close=close_price,
                volume=1000.0,
                is_closed=True,
                source="test",
            )
        )
        base = close_price
    return tuple(result)


def test_fresh_break_has_low_travel_and_large_remaining_room() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(0.2, 0.3, 0.4)),
        features=FeatureSnapshot(atr=2.0, ema_fast=100.0, vwap=99.8),
        direction=TradeDirection.LONG,
        current_price=100.8,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.state is ContinuationState.FRESH_BREAK
    assert result.impulse_travel_atr == pytest.approx(0.4)
    assert result.remaining_target_room_atr == pytest.approx(2.6)


def test_first_continuation_can_qualify_before_objective_is_mature() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(0.5, 0.6, 0.7)),
        features=FeatureSnapshot(atr=2.0, ema_fast=100.8, vwap=100.5),
        direction=TradeDirection.LONG,
        current_price=102.0,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.state is ContinuationState.FIRST_CONTINUATION
    assert result.objective_consumption == pytest.approx(1 / 3)


def test_mature_continuation_is_measurably_downgraded() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(0.8, 0.7, 0.6)),
        features=FeatureSnapshot(atr=2.0, ema_fast=101.0, vwap=100.5),
        direction=TradeDirection.LONG,
        current_price=104.0,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.state is ContinuationState.MATURE_CONTINUATION
    assert result.objective_consumption == pytest.approx(2 / 3)


def test_late_decelerating_chase_is_exhausted() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(1.0, 0.6, 0.2)),
        features=FeatureSnapshot(atr=2.0, ema_fast=102.0, vwap=101.5),
        direction=TradeDirection.LONG,
        current_price=105.4,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.state is ContinuationState.EXHAUSTED
    assert result.momentum_decelerating is True
    assert result.remaining_target_room_atr == pytest.approx(0.3)


def test_short_measurements_use_directional_geometry() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(-0.8, -0.5, -0.2)),
        features=FeatureSnapshot(atr=2.0, ema_fast=99.0, vwap=99.5),
        direction=TradeDirection.SHORT,
        current_price=95.0,
        impulse_origin=100.0,
        target_price=94.0,
    )

    assert result.state is ContinuationState.EXHAUSTED
    assert result.objective_consumption == pytest.approx(5 / 6)
    assert result.ema_extension_atr == pytest.approx(2.0)


def test_exhausted_state_blocks_new_continuation() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(1.0, 0.6, 0.2)),
        features=FeatureSnapshot(atr=2.0, ema_fast=102.0, vwap=101.5),
        direction=TradeDirection.LONG,
        current_price=105.4,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.allows_new_continuation is False
    assert result.requires_conditional_entry is False


def test_mature_state_requires_conditional_entry_without_becoming_exhausted() -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(0.8, 0.7, 0.6)),
        features=FeatureSnapshot(atr=2.0, ema_fast=101.0, vwap=100.5),
        direction=TradeDirection.LONG,
        current_price=104.0,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.allows_new_continuation is True
    assert result.requires_conditional_entry is True


@pytest.mark.parametrize("state_current", [100.8, 102.0])
def test_fresh_and_first_continuation_remain_allowed(
    state_current: float,
) -> None:
    result = measure_continuation_freshness(
        candles=_candles(bodies=(0.2, 0.3, 0.4)),
        features=FeatureSnapshot(atr=2.0, ema_fast=100.0, vwap=99.8),
        direction=TradeDirection.LONG,
        current_price=state_current,
        impulse_origin=100.0,
        target_price=106.0,
    )

    assert result.allows_new_continuation is True
    assert result.requires_conditional_entry is False
