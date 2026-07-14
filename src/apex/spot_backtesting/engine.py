"""Deterministic chronological simulator for long-only spot portfolios."""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from apex.spot_backtesting.contracts import (
    SpotBacktestConfig,
    SpotBacktestResult,
    SpotBar,
    SpotEquityPoint,
    SpotExitReason,
    SpotOrderPlan,
    SpotPosition,
    SpotTradeRecord,
)
from apex.spot_backtesting.metrics import compute_spot_portfolio_metrics


def run_spot_backtest(
    config: SpotBacktestConfig,
    plans: Sequence[SpotOrderPlan],
    bars: Sequence[SpotBar],
) -> SpotBacktestResult:
    """Replay all symbols in stable timestamp/symbol/plan order."""
    _validate_inputs(plans, bars)
    plan_map = {plan.plan_id: plan for plan in plans}
    positions = {plan.plan_id: SpotPosition(plan=plan) for plan in plans}
    cash = config.starting_cash
    trades: list[SpotTradeRecord] = []
    curve: list[SpotEquityPoint] = []
    latest: dict[str, float] = {}

    for bar in sorted(bars, key=lambda item: (item.timestamp, item.symbol)):
        latest[bar.symbol] = bar.close
        relevant = sorted(
            (plan for plan in plans if plan.symbol == bar.symbol),
            key=lambda plan: plan.plan_id,
        )
        for plan in relevant:
            position = positions[plan.plan_id]
            if position.closed_at is not None:
                continue
            cash = _process_position(config, position, bar, cash, trades)
        curve.append(_equity_point(bar.timestamp, cash, positions, latest))

    if bars:
        final_time = max(bar.timestamp for bar in bars)
        for plan_id in sorted(plan_map):
            position = positions[plan_id]
            if position.quantity <= 0.0 or position.closed_at is not None:
                continue
            mark = latest.get(position.plan.symbol)
            if mark is None:
                continue
            cash = _close_position(
                config, position, mark, final_time, cash, SpotExitReason.FINAL_MARK, trades
            )
        curve.append(_equity_point(final_time, cash, positions, latest))

    metrics = compute_spot_portfolio_metrics(
        trades, curve, starting_cash=config.starting_cash
    )
    return SpotBacktestResult(
        config=config,
        starting_cash=config.starting_cash,
        current_cash=cash,
        portfolio_equity=metrics.ending_equity,
        trades=tuple(trades),
        equity_curve=tuple(curve),
        metrics=metrics,
    )


def _validate_inputs(
    plans: Sequence[SpotOrderPlan], bars: Sequence[SpotBar]
) -> None:
    identifiers = [plan.plan_id for plan in plans]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("spot plan ids must be unique")
    symbols = {plan.symbol for plan in plans}
    missing = symbols - {bar.symbol for bar in bars}
    if missing:
        raise ValueError(f"missing bars for planned symbols: {sorted(missing)}")


def _process_position(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
    trades: list[SpotTradeRecord],
) -> float:
    plan = position.plan
    if position.quantity <= 0.0 and bar.timestamp > plan.expires_at:
        position.closed_at = bar.timestamp
        return cash
    if position.quantity > 0.0:
        if bar.regime in plan.exit_regimes:
            return _close_position(
                config, position, bar.open, bar.timestamp, cash, SpotExitReason.REGIME, trades
            )
        holding = plan.maximum_holding or config.maximum_holding
        if position.opened_at is not None and bar.timestamp - position.opened_at >= holding:
            return _close_position(
                config, position, bar.open, bar.timestamp, cash, SpotExitReason.TIME, trades
            )
        if bar.low <= plan.protective_stop:
            return _close_position(
                config,
                position,
                plan.protective_stop,
                bar.timestamp,
                cash,
                SpotExitReason.STOP,
                trades,
            )

    cash = _fill_entries(config, position, bar, cash)
    if position.quantity > 0.0:
        cash = _fill_targets(config, position, bar, cash, trades)
    return cash


def _fill_entries(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
) -> float:
    plan = position.plan
    if not config.allow_scale_in and position.filled_entry_indices:
        return cash
    if len(position.filled_entry_indices) >= config.maximum_scale_entries:
        return cash
    for index, entry in enumerate(plan.entries):
        if index in position.filled_entry_indices or entry.trigger_at > bar.timestamp:
            continue
        if not bar.low <= entry.price <= bar.high:
            continue
        if position.filled_entry_indices and entry.price >= position.average_entry:
            continue
        current_positions = _open_position_count(position)
        if position.quantity <= 0.0 and current_positions >= config.maximum_concurrent_positions:
            continue
        target_cash = config.starting_cash * plan.allocation_pct / 100.0
        target_cash = min(
            target_cash,
            config.starting_cash * config.maximum_allocation_per_position_pct / 100.0,
        )
        leg_cash = target_cash * entry.allocation_fraction
        reserve = config.starting_cash * config.minimum_cash_reserve_pct / 100.0
        available = max(0.0, cash - reserve)
        leg_cash = min(leg_cash, available)
        if leg_cash <= 0.0:
            continue
        fill_price = entry.price * (1.0 + config.slippage_pct / 100.0)
        fee = leg_cash * config.fee_pct / 100.0
        total = leg_cash + fee
        if total > cash:
            continue
        quantity = leg_cash / fill_price
        position.quantity += quantity
        position.cost_basis += leg_cash
        position.entry_fees += fee
        position.filled_entry_indices.add(index)
        position.opened_at = position.opened_at or bar.timestamp
        cash -= total
    return cash


def _fill_targets(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
    trades: list[SpotTradeRecord],
) -> float:
    initial_quantity = position.quantity
    for index, target in enumerate(position.plan.targets):
        if index in position.filled_target_indices or bar.high < target.price:
            continue
        quantity = min(position.quantity, initial_quantity * target.fraction)
        if quantity <= 0.0:
            continue
        fill = target.price * (1.0 - config.slippage_pct / 100.0)
        gross = quantity * fill
        fee = gross * config.fee_pct / 100.0
        basis = position.average_entry * quantity
        position.quantity -= quantity
        position.cost_basis -= basis
        position.realized_pnl += gross - fee - basis
        position.filled_target_indices.add(index)
        cash += gross - fee
    if position.quantity <= 1e-12:
        position.quantity = 0.0
        position.cost_basis = 0.0
        _record_closed(position, bar.timestamp, cash, SpotExitReason.TARGET, trades)
    return cash


def _close_position(
    config: SpotBacktestConfig,
    position: SpotPosition,
    price: float,
    timestamp: datetime,
    cash: float,
    reason: SpotExitReason,
    trades: list[SpotTradeRecord],
) -> float:
    fill = price * (1.0 - config.slippage_pct / 100.0)
    gross = position.quantity * fill
    fee = gross * config.fee_pct / 100.0
    basis = position.cost_basis
    position.realized_pnl += gross - fee - basis
    position.quantity = 0.0
    position.cost_basis = 0.0
    cash += gross - fee
    _record_closed(position, timestamp, cash, reason, trades)
    return cash


def _record_closed(
    position: SpotPosition,
    timestamp: datetime,
    cash: float,
    reason: SpotExitReason,
    trades: list[SpotTradeRecord],
) -> None:
    del cash
    position.closed_at = timestamp
    if position.opened_at is None:
        return
    invested = max(position.entry_fees, 0.0)
    invested += sum(
        entry.price * entry.allocation_fraction for entry in position.plan.entries
    )
    invested = max(invested, 1e-12)
    trades.append(
        SpotTradeRecord(
            plan_id=position.plan.plan_id,
            symbol=position.plan.symbol,
            strategy=position.plan.strategy,
            score_band=position.plan.score_band,
            market_regime=position.plan.market_regime.value,
            opened_at=position.opened_at,
            closed_at=timestamp,
            invested_cash=invested,
            proceeds=invested + position.realized_pnl,
            net_pnl=position.realized_pnl - position.entry_fees,
            return_pct=(position.realized_pnl - position.entry_fees) / invested * 100.0,
            holding_duration_seconds=(timestamp - position.opened_at).total_seconds(),
            exit_reason=reason,
        )
    )


def _equity_point(
    timestamp: datetime,
    cash: float,
    positions: dict[str, SpotPosition],
    latest: dict[str, float],
) -> SpotEquityPoint:
    market_value = sum(
        position.quantity * latest.get(position.plan.symbol, position.average_entry)
        for position in positions.values()
        if position.quantity > 0.0
    )
    equity = cash + market_value
    exposure = market_value / equity * 100.0 if equity > 0.0 else 0.0
    concurrent = sum(position.quantity > 0.0 for position in positions.values())
    return SpotEquityPoint(timestamp, cash, market_value, equity, exposure, concurrent)


def _open_position_count(position: SpotPosition) -> int:
    return 1 if position.quantity > 0.0 else 0
