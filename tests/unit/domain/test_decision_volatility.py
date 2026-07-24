from __future__ import annotations

from datetime import UTC, datetime, timedelta

from apex.domain.decision_volatility import (
    DecisionVolatilityClass,
    build_decision_volatility_profile,
)
from apex.domain.models import Candle


def _candles(ranges: list[float]) -> tuple[Candle, ...]:
    start = datetime(2026, 1, 1, tzinfo=UTC)
    price = 100.0
    result = []
    for index, width in enumerate(ranges):
        open_time = start + timedelta(minutes=5 * index)
        close = price + 0.05
        result.append(
            Candle(
                symbol="TESTUSDT",
                timeframe="5m",
                open_time=open_time,
                close_time=open_time + timedelta(minutes=5),
                open=price,
                high=max(price, close) + width / 2,
                low=min(price, close) - width / 2,
                close=close,
                volume=1000.0,
                is_closed=True,
                source="test",
            )
        )
        price = close
    return tuple(result)


def test_profile_supports_extreme() -> None:
    candles = _candles([0.4] * 70 + [4.0])
    profile = build_decision_volatility_profile(candles, decision_time=candles[-1].close_time)
    assert profile.available is True
    assert profile.volatility_class is DecisionVolatilityClass.EXTREME


def test_future_candles_do_not_change_profile() -> None:
    history = _candles([0.5] * 50 + [1.5])
    decision_time = history[-1].close_time
    future = _candles([8.0] * 10)
    shifted = tuple(
        candle.model_copy(
            update={
                "open_time": decision_time + timedelta(minutes=5 * (index + 1)),
                "close_time": decision_time + timedelta(minutes=5 * (index + 2)),
            }
        )
        for index, candle in enumerate(future)
    )
    assert build_decision_volatility_profile(
        history, decision_time=decision_time
    ) == build_decision_volatility_profile((*history, *shifted), decision_time=decision_time)


def test_insufficient_history_is_explicit() -> None:
    candles = _candles([0.5] * 20)
    profile = build_decision_volatility_profile(candles, decision_time=candles[-1].close_time)
    assert profile.available is False
    assert profile.unavailable_reason == "insufficient_history"
