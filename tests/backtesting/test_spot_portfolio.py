"""Deterministic coverage for the separate long-only spot simulator."""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.spot_backtesting import (
    SpotBacktestConfig,
    SpotBar,
    SpotEntryLeg,
    SpotExitReason,
    SpotMarketRegime,
    SpotOrderPlan,
    SpotTarget,
    run_spot_backtest,
)


START = datetime(2026, 1, 1, tzinfo=UTC)


def _plan(
    plan_id: str = "plan-a",
    symbol: str = "BTCUSDT",
    *,
    allocation_pct: float = 20.0,
    entries: tuple[SpotEntryLeg, ...] | None = None,
    targets: tuple[SpotTarget, ...] | None = None,
    stop: float = 90.0,
) -> SpotOrderPlan:
    return SpotOrderPlan(
        plan_id=plan_id,
        symbol=symbol,
        strategy="higher_timeframe_trend_pullback",
        score_band="80-89",
        market_regime=SpotMarketRegime.RISK_ON,
        created_at=START,
        expires_at=START + timedelta(days=2),
        allocation_pct=allocation_pct,
        entries=entries or (SpotEntryLeg(100.0, 1.0, START),),
        targets=targets or (SpotTarget(110.0, 1.0, "TP1"),),
        protective_stop=stop,
    )


def _bar(
    timestamp: datetime,
    symbol: str = "BTCUSDT",
    *,
    open_price: float = 100.0,
    high: float = 101.0,
    low: float = 99.0,
    close: float = 100.0,
    regime: SpotMarketRegime = SpotMarketRegime.RISK_ON,
) -> SpotBar:
    return SpotBar(symbol, timestamp, open_price, high, low, close, regime)


def test_spot_contract_is_long_only_and_has_no_futures_leakage() -> None:
    with pytest.raises(ValueError, match="long-only"):
        _plan(entries=(SpotEntryLeg(89.0, 1.0, START),))
    config = SpotBacktestConfig(starting_cash=10_000.0)
    assert not hasattr(config, "leverage")
    assert not hasattr(config, "liquidation_price")
    assert not hasattr(config, "margin")


def test_entry_and_exit_costs_reduce_return() -> None:
    bars = (
        _bar(START),
        _bar(START + timedelta(days=1), high=112.0, low=99.0, close=110.0),
    )
    free = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(),),
        bars,
    )
    costly = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.2, slippage_pct=0.2),
        (_plan(),),
        bars,
    )
    assert free.trades[0].return_pct > costly.trades[0].return_pct
    assert costly.current_cash < free.current_cash


def test_per_position_allocation_cap_and_insufficient_cash_are_enforced() -> None:
    result = run_spot_backtest(
        SpotBacktestConfig(
            starting_cash=1_000.0,
            maximum_allocation_per_position_pct=10.0,
            maximum_total_exposure_pct=90.0,
            minimum_cash_reserve_pct=80.0,
            fee_pct=0.0,
            slippage_pct=0.0,
        ),
        (_plan(allocation_pct=60.0),),
        (_bar(START), _bar(START + timedelta(days=1), close=100.0)),
    )
    assert result.trades[0].invested_cash == pytest.approx(100.0)
    assert result.metrics.maximum_exposure_pct <= 10.1


def test_total_exposure_and_concurrent_position_caps_are_portfolio_wide() -> None:
    plans = (
        _plan("a", "ADAUSDT", allocation_pct=30.0),
        _plan("b", "BTCUSDT", allocation_pct=30.0),
    )
    bars = (
        _bar(START, "BTCUSDT"),
        _bar(START, "ADAUSDT"),
        _bar(START + timedelta(days=1), "BTCUSDT"),
        _bar(START + timedelta(days=1), "ADAUSDT"),
    )
    exposure_limited = run_spot_backtest(
        SpotBacktestConfig(
            starting_cash=10_000.0,
            maximum_allocation_per_position_pct=30.0,
            maximum_total_exposure_pct=40.0,
            maximum_concurrent_positions=2,
            fee_pct=0.0,
            slippage_pct=0.0,
        ),
        plans,
        bars,
    )
    assert exposure_limited.metrics.maximum_exposure_pct <= 40.1

    concurrency_limited = run_spot_backtest(
        SpotBacktestConfig(
            starting_cash=10_000.0,
            maximum_allocation_per_position_pct=30.0,
            maximum_total_exposure_pct=60.0,
            maximum_concurrent_positions=1,
            fee_pct=0.0,
            slippage_pct=0.0,
        ),
        plans,
        bars,
    )
    assert concurrency_limited.metrics.maximum_concurrent_positions == 1
    assert concurrency_limited.metrics.trade_count == 1


def test_planned_lower_scale_in_is_allowed_but_uncontrolled_higher_buy_is_blocked() -> None:
    lower_entries = (
        SpotEntryLeg(100.0, 0.5, START),
        SpotEntryLeg(95.0, 0.5, START + timedelta(hours=1)),
    )
    lower = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(entries=lower_entries),),
        (
            _bar(START),
            _bar(START + timedelta(hours=1), high=100.0, low=94.0, close=96.0),
            _bar(START + timedelta(days=1), high=101.0, low=96.0, close=100.0),
        ),
    )
    assert lower.trades[0].invested_cash == pytest.approx(2_000.0)

    higher_entries = (
        SpotEntryLeg(100.0, 0.5, START),
        SpotEntryLeg(105.0, 0.5, START + timedelta(hours=1)),
    )
    higher = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(entries=higher_entries),),
        (
            _bar(START),
            _bar(START + timedelta(hours=1), high=106.0, low=99.0, close=105.0),
            _bar(START + timedelta(days=1), high=106.0, low=100.0, close=105.0),
        ),
    )
    assert higher.trades[0].invested_cash == pytest.approx(1_000.0)


def test_partial_exit_then_final_mark_preserves_exact_accounting() -> None:
    plan = _plan(
        targets=(
            SpotTarget(105.0, 0.5, "TP1"),
            SpotTarget(120.0, 0.5, "TP2"),
        )
    )
    result = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (plan,),
        (
            _bar(START),
            _bar(START + timedelta(days=1), high=106.0, low=99.0, close=105.0),
            _bar(START + timedelta(days=2), high=109.0, low=104.0, close=108.0),
        ),
    )
    trade = result.trades[0]
    assert trade.exit_reason is SpotExitReason.FINAL_MARK
    assert trade.proceeds == pytest.approx(2_130.0)
    assert trade.net_pnl == pytest.approx(130.0)


def test_stop_wins_same_bar_ambiguity_and_regime_exit_is_supported() -> None:
    stopped = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(),),
        (
            _bar(START),
            _bar(START + timedelta(days=1), high=115.0, low=85.0, close=110.0),
        ),
    )
    assert stopped.trades[0].exit_reason is SpotExitReason.STOP
    assert stopped.trades[0].net_pnl < 0.0

    regime = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(),),
        (
            _bar(START),
            _bar(
                START + timedelta(days=1),
                open_price=98.0,
                high=99.0,
                low=97.0,
                close=98.0,
                regime=SpotMarketRegime.RISK_OFF,
            ),
        ),
    )
    assert regime.trades[0].exit_reason is SpotExitReason.REGIME


def test_same_timestamp_ordering_is_deterministic() -> None:
    config = SpotBacktestConfig(
        starting_cash=10_000.0,
        maximum_allocation_per_position_pct=30.0,
        maximum_total_exposure_pct=30.0,
        maximum_concurrent_positions=2,
        fee_pct=0.0,
        slippage_pct=0.0,
    )
    plans = (_plan("b", "BTCUSDT", allocation_pct=30.0), _plan("a", "ADAUSDT", allocation_pct=30.0))
    bars = (_bar(START, "BTCUSDT"), _bar(START, "ADAUSDT"))
    forward = run_spot_backtest(config, plans, bars)
    reverse = run_spot_backtest(config, tuple(reversed(plans)), tuple(reversed(bars)))
    assert forward.trades == reverse.trades
    assert forward.equity_curve == reverse.equity_curve


def test_portfolio_drawdown_and_exposure_metrics_are_computed() -> None:
    result = run_spot_backtest(
        SpotBacktestConfig(starting_cash=10_000.0, fee_pct=0.0, slippage_pct=0.0),
        (_plan(stop=80.0),),
        (
            _bar(START),
            _bar(START + timedelta(days=1), high=101.0, low=94.0, close=95.0),
            _bar(START + timedelta(days=2), high=101.0, low=94.0, close=100.0),
        ),
    )
    assert result.metrics.maximum_drawdown_pct > 0.0
    assert result.metrics.average_exposure_pct > 0.0
    assert result.metrics.maximum_concurrent_positions == 1
