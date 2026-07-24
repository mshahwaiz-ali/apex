"""Focused tests for the shared sweep/reclaim evaluator."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.domain.models import Candle
from apex.domain.sweep_reclaim import (
    SweepReclaimPolicy,
    SweepReclaimState,
    evaluate_sweep_reclaim,
)
from apex.strategies import TradeDirection


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


def test_shallow_long_sweep_reclaim_and_retest_is_authorized() -> None:
    assessment = evaluate_sweep_reclaim(
        direction=TradeDirection.LONG,
        entry_price=100.0,
        invalidation_price=99.0,
        target_price=103.0,
        sweep_candle=_candle(
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
    assert assessment.shallow_sweep is True
    assert assessment.deep_failure is False
    assert assessment.reclaim_confirmed is True
    assert assessment.retest_confirmed is True
    assert assessment.recovery_entry_authorized is True
    assert assessment.maximum_breach_r == pytest.approx(0.2)
    assert assessment.bars_to_entry_reclaim == 1
    assert assessment.reclaim_entry_price == pytest.approx(100.6)
    assert assessment.rejected_reason == "none"


def test_strong_reclaim_without_retest_remains_reclaim_confirmed_only() -> None:
    assessment = evaluate_sweep_reclaim(
        direction=TradeDirection.LONG,
        entry_price=100.0,
        invalidation_price=99.0,
        target_price=103.0,
        sweep_candle=_candle(
            0,
            open_price=99.4,
            high=99.7,
            low=98.8,
            close=99.2,
        ),
        confirmation_candles=(
            _candle(
                1,
                open_price=99.2,
                high=101.0,
                low=99.1,
                close=100.8,
            ),
            _candle(
                2,
                open_price=100.8,
                high=101.4,
                low=100.5,
                close=101.2,
            ),
        ),
    )

    assert assessment.state is SweepReclaimState.RECLAIM_CONFIRMED
    assert assessment.reclaim_confirmed is True
    assert assessment.retest_confirmed is False
    assert assessment.recovery_entry_authorized is False
    assert assessment.rejected_reason == "reclaim_not_retested"


def test_deep_directional_failure_is_rejected() -> None:
    assessment = evaluate_sweep_reclaim(
        direction=TradeDirection.LONG,
        entry_price=100.0,
        invalidation_price=99.0,
        target_price=103.0,
        sweep_candle=_candle(
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

    assert assessment.state is SweepReclaimState.DEEP_FAILURE
    assert assessment.deep_failure is True
    assert assessment.reclaim_confirmed is False
    assert assessment.recovery_entry_authorized is False
    assert assessment.rejected_reason == "deep_directional_failure"


def test_short_sweep_uses_inverse_geometry() -> None:
    assessment = evaluate_sweep_reclaim(
        direction=TradeDirection.SHORT,
        entry_price=100.0,
        invalidation_price=101.0,
        target_price=97.0,
        sweep_candle=_candle(
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

    assert assessment.state is SweepReclaimState.RETEST_CONFIRMED
    assert assessment.shallow_sweep is True
    assert assessment.maximum_breach_r == pytest.approx(0.2)
    assert assessment.recovery_entry_authorized is True


def test_slow_reclaim_expires() -> None:
    policy = SweepReclaimPolicy(
        deep_reclaim_bars=5,
        reclaim_max_confirm_bars=2,
    )
    assessment = evaluate_sweep_reclaim(
        direction=TradeDirection.LONG,
        entry_price=100.0,
        invalidation_price=99.0,
        target_price=104.0,
        sweep_candle=_candle(
            0,
            open_price=99.3,
            high=99.5,
            low=98.8,
            close=99.1,
        ),
        confirmation_candles=(
            _candle(
                1,
                open_price=99.1,
                high=99.6,
                low=99.0,
                close=99.4,
            ),
            _candle(
                2,
                open_price=99.4,
                high=99.8,
                low=99.2,
                close=99.6,
            ),
            _candle(
                3,
                open_price=99.6,
                high=100.9,
                low=99.5,
                close=100.7,
            ),
        ),
        policy=policy,
    )

    assert assessment.state is SweepReclaimState.EXPIRED
    assert assessment.reclaim_confirmed is False
    assert assessment.rejected_reason == "reclaim_too_slow"


def test_policy_rejects_inverted_thresholds() -> None:
    with pytest.raises(ValueError, match="deep breach threshold"):
        SweepReclaimPolicy(
            shallow_breach_max_r=0.7,
            deep_breach_min_r=0.6,
        )
