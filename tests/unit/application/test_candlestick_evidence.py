"""Tests for contextual candlestick evidence."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from apex.application.candlestick_evidence import (
    CandleCompletionState,
    CandlePatternDirection,
    candlestick_evidence_observations,
    detect_contextual_candlesticks,
)
from apex.application.methodology_contracts import EvidenceFamily
from apex.domain.models import Candle
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
    volume: float = 1_000.0,
    is_closed: bool = True,
) -> Candle:
    opened = datetime(2026, 1, 1, tzinfo=UTC) + timedelta(minutes=15 * index)
    return Candle(
        symbol="BTCUSDT",
        timeframe="15m",
        open_time=opened,
        close_time=opened + timedelta(minutes=15),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=volume,
        is_closed=is_closed,
        source="test",
    )


def _context(candles: tuple[Candle, ...], *, range_position: float = 0.2) -> StrategyContext:
    frame = TimeframeContext(
        timeframe="15m",
        role=TimeframeRole.SETUP,
        current_price=candles[-1].close,
        features=FeatureSnapshot(
            atr=1.0,
            range_position=range_position,
        ),
        structure=SimpleNamespace(
            trend=SimpleNamespace(direction=SimpleNamespace(value="bearish"))
        ),
        liquidity=SimpleNamespace(),
        recent_candles=candles,
        active_candle=not candles[-1].is_closed,
    )
    return StrategyContext(symbol="BTCUSDT", frames=(frame,))


def test_hammer_requires_decline_context_and_does_not_generate_target() -> None:
    candles = (
        _candle(0, open_price=105, high=106, low=104, close=104),
        _candle(1, open_price=104, high=105, low=102, close=102.5),
        _candle(2, open_price=102.5, high=103, low=100, close=100.5),
        _candle(3, open_price=100.4, high=101.0, low=97.0, close=100.8, volume=1_800),
    )

    patterns = detect_contextual_candlesticks(_context(candles))

    hammer = next(item for item in patterns if item.pattern_id == "hammer")
    assert hammer.pattern_direction is CandlePatternDirection.BULLISH
    assert hammer.completion_state is CandleCompletionState.COMPLETED
    assert hammer.confirmation_level == candles[-1].high
    assert hammer.invalidation_level == candles[-1].low
    assert hammer.standalone_trade_approval is False
    assert hammer.target_source == "none; candlestick evidence does not generate targets"


def test_active_hammer_is_provisional_evidence() -> None:
    candles = (
        _candle(0, open_price=105, high=106, low=104, close=104),
        _candle(1, open_price=104, high=105, low=102, close=102.5),
        _candle(2, open_price=102.5, high=103, low=100, close=100.5),
        _candle(
            3,
            open_price=100.4,
            high=101.0,
            low=97.0,
            close=100.8,
            is_closed=False,
        ),
    )

    patterns = detect_contextual_candlesticks(_context(candles))

    hammer = next(item for item in patterns if item.pattern_id == "hammer")
    assert hammer.completion_state is CandleCompletionState.PROVISIONAL


def test_bullish_engulfing_maps_to_candle_evidence_family() -> None:
    candles = (
        _candle(0, open_price=106, high=107, low=105, close=105.2),
        _candle(1, open_price=105.2, high=106, low=103, close=103.5),
        _candle(2, open_price=103.5, high=104, low=101, close=102.0),
        _candle(3, open_price=101.8, high=105.0, low=101.0, close=104.8),
    )

    patterns = detect_contextual_candlesticks(_context(candles))
    observations = candlestick_evidence_observations(patterns)

    assert any(item.pattern_id == "bullish_engulfing" for item in patterns)
    assert all(item.family is EvidenceFamily.CANDLE for item in observations)
    assert {item.independence_group for item in observations} == {"candlestick_context"}
