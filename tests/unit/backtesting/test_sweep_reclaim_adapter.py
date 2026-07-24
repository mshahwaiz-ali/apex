"""Focused tests for the backtest sweep/reclaim adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.contracts import BacktestSignal
from apex.backtesting.sweep_reclaim_adapter import (
    assess_post_stop_sweep_reclaim,
    sweep_reclaim_metadata,
)
from apex.domain.models import Candle
from apex.domain.sweep_reclaim import SweepReclaimState
from apex.strategies import StrategyType, TradeDirection

_BASE_TIME = datetime(2026, 7, 24, 12, 0, tzinfo=UTC)


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
        entry = 100.0
        stop = 99.0
        target = 103.0
    else:
        entry = 100.0
        stop = 101.0
        target = 97.0
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


def test_adapter_returns_shared_retest_assessment() -> None:
    signal = _signal(TradeDirection.LONG)
    assessment = assess_post_stop_sweep_reclaim(
        signal,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
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

    assert assessment.state is SweepReclaimState.RETEST_CONFIRMED
    assert assessment.recovery_entry_authorized is True
    assert assessment.maximum_breach_r == pytest.approx(0.2)


def test_metadata_maps_shared_assessment_to_legacy_keys() -> None:
    signal = _signal(TradeDirection.SHORT)
    assessment = assess_post_stop_sweep_reclaim(
        signal,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
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

    metadata = sweep_reclaim_metadata(assessment)

    assert metadata["shared_sweep_reclaim_state"] == "retest_confirmed"
    assert metadata["shallow_stop_sweep"] is True
    assert metadata["deep_directional_failure"] is False
    assert metadata["sweep_reclaim_candidate"] is True
    assert metadata["sweep_reclaim_confirmed"] is True
    assert metadata["recovery_entry_authorized"] is True
    assert metadata["post_stop_maximum_excursion_beyond_stop_r"] == pytest.approx(0.2)
    assert metadata["post_stop_bars_to_reclaim"] == 1
    assert metadata["recovery_entry_price"] == pytest.approx(99.3)


def test_deep_failure_metadata_never_authorizes_recovery() -> None:
    signal = _signal(TradeDirection.LONG)
    assessment = assess_post_stop_sweep_reclaim(
        signal,
        entry_price=signal.entry_price,
        stop_price=signal.stop_price,
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
        ),
    )

    metadata = sweep_reclaim_metadata(assessment)

    assert metadata["shared_sweep_reclaim_state"] == "deep_failure"
    assert metadata["deep_directional_failure"] is True
    assert metadata["sweep_reclaim_candidate"] is False
    assert metadata["sweep_reclaim_confirmed"] is False
    assert metadata["recovery_entry_authorized"] is False
    assert metadata["sweep_reclaim_rejected_reason"] == "deep_directional_failure"
