from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime, timedelta

import pytest

from apex.application.spot_historical_backtest import (
    SpotBacktestConfig,
    _Order,
    _Wallet,
    _fill_entries,
    _metrics,
    _process_exits,
    _trade_record,
)
from apex.domain.models import Candle


def _candle(*, low: float, high: float, close: float, hour: int = 1) -> Candle:
    opened = datetime(2026, 1, 1, hour, tzinfo=UTC)
    return Candle(
        symbol="BTCUSDT",
        timeframe="1h",
        open_time=opened,
        close_time=opened + timedelta(hours=1),
        open=close,
        high=high,
        low=low,
        close=close,
        volume=100.0,
        is_closed=True,
        source="test",
    )


def _order() -> _Order:
    decision = datetime(2026, 1, 1, tzinfo=UTC)
    return _Order(
        order_id="BTCUSDT:test",
        symbol="BTCUSDT",
        decision_time=decision,
        expires_at=decision + timedelta(hours=48),
        strategy="TREND_PULLBACK",
        regime="RISK_ON",
        eligibility_state="ELIGIBLE",
        entry_state="READY_NOW",
        entries=[
            {"label": "ENTRY_1", "price": 100.0, "allocation_percentage": 60.0},
            {"label": "ENTRY_2", "price": 95.0, "allocation_percentage": 40.0},
        ],
        stop_price=90.0,
        targets=[
            {"label": "TP1", "price": 110.0, "sell_percentage": 50.0},
            {"label": "TP2", "price": 120.0, "sell_percentage": 50.0},
        ],
        maximum_chase_price=103.0,
        invalidation_price=89.0,
        capital_budget=1_000.0,
    )


def test_partial_entries_and_targets_use_position_level_accounting() -> None:
    order = _order()
    wallet = _Wallet(cash=2_000.0)
    counters: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, object]] = []
    config = SpotBacktestConfig(fee_rate=0.001, slippage_rate=0.0)

    assert _fill_entries(order, _candle(low=99.0, high=101.0, close=100.0), wallet, config, counters, events)
    assert order.filled_labels == {"ENTRY_1"}
    assert order.entry_notional == pytest.approx(600.0)

    assert _fill_entries(order, _candle(low=94.0, high=96.0, close=95.0, hour=2), wallet, config, counters, events)
    assert order.filled_labels == {"ENTRY_1", "ENTRY_2"}
    assert order.entry_notional == pytest.approx(1_000.0)

    reason = _process_exits(
        order,
        _candle(low=105.0, high=111.0, close=109.0, hour=3),
        wallet,
        config,
        counters,
        events,
    )
    assert reason is None
    assert order.completed_targets == {"TP1"}
    assert order.remaining_quantity == pytest.approx(order.quantity * 0.5)

    reason = _process_exits(
        order,
        _candle(low=115.0, high=121.0, close=120.0, hour=4),
        wallet,
        config,
        counters,
        events,
    )
    assert reason == "FINAL_TARGET"
    trade = _trade_record(order, datetime(2026, 1, 1, 5, tzinfo=UTC), reason, wallet)
    assert trade["realized_pnl"] > 0
    assert trade["exit_fees"] > 0


def test_ambiguous_candle_policy_is_conservative_by_default() -> None:
    order = _order()
    wallet = _Wallet(cash=2_000.0)
    counters: defaultdict[str, int] = defaultdict(int)
    events: list[dict[str, object]] = []
    config = SpotBacktestConfig(fee_rate=0.0, slippage_rate=0.0)
    assert _fill_entries(order, _candle(low=99.0, high=101.0, close=100.0), wallet, config, counters, events)

    reason = _process_exits(
        order,
        _candle(low=89.0, high=111.0, close=100.0, hour=2),
        wallet,
        config,
        counters,
        events,
    )

    assert reason == "STOP_LOSS"
    assert counters["ambiguous_candle_count"] == 1
    assert order.realized_pnl < 0


def test_metrics_use_trade_pnl_and_exposure_curve() -> None:
    wallet = _Wallet(cash=1_050.0, fees=5.0, slippage_cost=2.0)
    trades = (
        {
            "realized_pnl": 100.0,
            "opened_at": "2026-01-01T00:00:00+00:00",
            "closed_at": "2026-01-01T02:00:00+00:00",
            "symbol": "BTCUSDT",
            "strategy": "A",
            "market_regime": "RISK_ON",
            "eligibility_state": "ELIGIBLE",
            "entry_state": "READY_NOW",
            "exit_reason": "FINAL_TARGET",
        },
        {
            "realized_pnl": -50.0,
            "opened_at": "2026-01-02T00:00:00+00:00",
            "closed_at": "2026-01-02T04:00:00+00:00",
            "symbol": "ETHUSDT",
            "strategy": "B",
            "market_regime": "NEUTRAL",
            "eligibility_state": "INELIGIBLE",
            "entry_state": "WAIT_FOR_RETEST",
            "exit_reason": "STOP_LOSS",
        },
    )
    curve = (
        {"equity": 1_000.0, "exposure_utilization": 0.0},
        {"equity": 900.0, "exposure_utilization": 0.5},
        {"equity": 1_050.0, "exposure_utilization": 0.0},
    )

    metrics = _metrics(1_000.0, wallet, trades, curve, {"trade_count": 2})

    assert metrics["gross_profit"] == 100.0
    assert metrics["gross_loss"] == -50.0
    assert metrics["profit_factor"] == 2.0
    assert metrics["win_rate"] == 0.5
    assert metrics["expectancy"] == 25.0
    assert metrics["maximum_drawdown"] == pytest.approx(0.1)
    assert metrics["maximum_exposure_utilization"] == 0.5
