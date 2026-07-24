"""Parity checks between legacy engine diagnostics and the shared evaluator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.contracts import BacktestConfig, BacktestSignal
from apex.backtesting.engine import _post_stop_thesis_metadata
from apex.backtesting.sweep_reclaim_adapter import (
    assess_post_stop_sweep_reclaim,
    sweep_reclaim_metadata,
)
from apex.domain.models import Candle
from apex.strategies import StrategyType, TradeDirection


_BASE_TIME = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)
_PARITY_KEYS = (
    "post_stop_maximum_excursion_beyond_stop_r",
    "post_stop_maximum_close_beyond_stop_r",
    "post_stop_bars_closed_beyond_stop",
    "post_stop_max_consecutive_closes_beyond_stop",
    "post_stop_stop_reclaimed",
    "post_stop_bars_to_stop_reclaim",
    "post_stop_entry_reclaimed",
    "post_stop_bars_to_reclaim",
    "shallow_stop_sweep",
    "wick_only_stop_sweep",
    "deep_directional_failure",
    "sweep_reclaim_candidate",
    "sweep_reclaim_confirmed",
    "sweep_reclaim_rejected_reason",
    "reclaim_candle_body_ratio",
    "reclaim_close_location",
    "entry_level_reclaimed",
    "retest_held",
    "remaining_target_room_r",
    "recovery_entry_authorized",
    "recovery_entry_price",
    "recovery_entry_candle",
)


def _candle(
    index: int,
    *,
    open_price: float,
    high: float,
    low: float,
    close: float,
) -> Candle:
    open_time = _BASE_TIME + timedelta(minutes=5 * index)
    return Candle(
        symbol="TEST/USDT",
        timeframe="5m",
        open_time=open_time,
        close_time=open_time + timedelta(minutes=5),
        open=open_price,
        high=high,
        low=low,
        close=close,
        volume=1_000.0,
        is_closed=True,
        source="unit-test",
    )


def _signal(direction: TradeDirection) -> BacktestSignal:
    if direction is TradeDirection.LONG:
        entry, stop, target = 100.0, 99.0, 103.0
    else:
        entry, stop, target = 100.0, 101.0, 97.0
    return BacktestSignal(
        symbol="TEST/USDT",
        strategy=StrategyType.BREAKOUT_RETEST,
        direction=direction,
        generated_at=_BASE_TIME,
        entry_price=entry,
        stop_price=stop,
        target_price=target,
        quantity=1.0,
        risk_amount=1.0,
        confidence_score=70.0,
    )


def _assert_parity(
    signal: BacktestSignal,
    *,
    stop_candle: Candle,
    confirmation_candles: tuple[Candle, ...],
) -> None:
    legacy = _post_stop_thesis_metadata(
        signal,
        confirmation_candles,
        entry=signal.entry_price,
        stop=signal.stop_price,
        stop_candle=stop_candle,
        config=BacktestConfig(),
    )
    shared = sweep_reclaim_metadata(
        assess_post_stop_sweep_reclaim(
            signal,
            entry_price=signal.entry_price,
            stop_price=signal.stop_price,
            stop_candle=stop_candle,
            confirmation_candles=confirmation_candles,
        )
    )

    for key in _PARITY_KEYS:
        legacy_value = legacy[key]
        shared_value = shared[key]
        if isinstance(legacy_value, float):
            assert isinstance(shared_value, int | float)
            assert float(shared_value) == pytest.approx(legacy_value), key
        else:
            assert shared_value == legacy_value, key


def test_shallow_long_reclaim_retest_matches_legacy() -> None:
    _assert_parity(
        _signal(TradeDirection.LONG),
        stop_candle=_candle(
            0,
            open_price=99.4,
            high=99.8,
            low=98.8,
            close=99.2,
        ),
        confirmation_candles=(
            _candle(
                1,
                open_price=99.2,
                high=100.8,
                low=99.1,
                close=100.6,
            ),
            _candle(
                2,
                open_price=100.6,
                high=100.9,
                low=99.8,
                close=100.4,
            ),
        ),
    )


def test_shallow_short_reclaim_retest_matches_legacy() -> None:
    _assert_parity(
        _signal(TradeDirection.SHORT),
        stop_candle=_candle(
            0,
            open_price=100.6,
            high=101.2,
            low=100.4,
            close=100.8,
        ),
        confirmation_candles=(
            _candle(
                1,
                open_price=100.8,
                high=100.9,
                low=99.1,
                close=99.3,
            ),
            _candle(
                2,
                open_price=99.3,
                high=100.2,
                low=99.0,
                close=99.6,
            ),
        ),
    )


def test_deep_failure_matches_legacy() -> None:
    _assert_parity(
        _signal(TradeDirection.LONG),
        stop_candle=_candle(
            0,
            open_price=99.2,
            high=99.4,
            low=98.1,
            close=98.4,
        ),
        confirmation_candles=(
            _candle(
                1,
                open_price=98.4,
                high=98.8,
                low=97.9,
                close=98.2,
            ),
            _candle(
                2,
                open_price=98.2,
                high=99.1,
                low=98.0,
                close=98.8,
            ),
        ),
    )
