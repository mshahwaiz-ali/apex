"""Deterministic chronological simulator for long-only spot portfolios."""

from __future__ import annotations

from collections import defaultdict
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
    """Replay all symbols with deterministic timestamp, symbol and plan ordering."""
    _validate_inputs(plans, bars)
    positions = {plan.plan_id: SpotPosition(plan=plan) for plan in plans}
    invested: dict[str, float] = defaultdict(float)
    proceeds: dict[str, float] = defaultdict(float)
    bought_quantity: dict[str, float] = defaultdict(float)
    cash = config.starting_cash
    trades: list[SpotTradeRecord] = []
    curve: list[SpotEquityPoint] = []
    latest: dict[str, float] = {}

    grouped: dict[datetime, list[SpotBar]] = defaultdict(list)
    for bar in bars:
        grouped[bar.timestamp].append(bar)

    for timestamp in sorted(grouped):
        timestamp_bars = sorted(grouped[timestamp], key=lambda item: item.symbol)
        for bar in timestamp_bars:
            latest[bar.symbol] = bar.close
        for bar in timestamp_bars:
            relevant = sorted(
                (plan for plan in plans if plan.symbol == bar.symbol),
                key=lambda plan: plan.plan_id,
            )
            for plan in relevant:
                position = positions[plan.plan_id]
                if position.closed_at is not None:
                    continue
                cash = _process_exits(
                    config,
                    position,
                    bar,
                    cash,
                    invested,
                    proceeds,
                    trades,
                )
        for bar in timestamp_bars:
            relevant = sorted(
                (plan for plan in plans if plan.symbol == bar.symbol),
                key=lambda plan: plan.plan_id,
            )
            for plan in relevant:
                position = positions[plan.plan_id]
                if position.closed_at is not None:
                    continue
                was_open = position.quantity > 0.0
                cash = _fill_entries(
                    config,
                    position,
                    bar,
                    cash,
                    positions,
                    latest,
                    invested,
                    bought_quantity,
                )
                if was_open:
                    cash = _fill_targets(
                        config,
                        position,
                        bar,
                        cash,
                        invested,
                        proceeds,
                        bought_quantity,
                        trades,
                    )
        curve.append(_equity_point(timestamp, cash, positions, latest))

    if bars:
        final_time = max(bar.timestamp for bar in bars)
        for plan_id in sorted(positions):
            position = positions[plan_id]
            mark = latest.get(position.plan.symbol)
            if position.quantity <= 0.0 or position.closed_at is not None or mark is None:
                continue
            cash = _close_position(
                config,
                position,
                mark,
                final_time,
                cash,
                SpotExitReason.FINAL_MARK,
                invested,
                proceeds,
                trades,
            )
        curve.append(_equity_point(final_time, cash, positions, latest))

    metrics = compute_spot_portfolio_metrics(trades, curve, starting_cash=config.starting_cash)
    return SpotBacktestResult(
        config=config,
        starting_cash=config.starting_cash,
        current_cash=cash,
        portfolio_equity=metrics.ending_equity,
        trades=tuple(trades),
        equity_curve=tuple(curve),
        metrics=metrics,
    )


def _validate_inputs(plans: Sequence[SpotOrderPlan], bars: Sequence[SpotBar]) -> None:
    identifiers = [plan.plan_id for plan in plans]
    if len(set(identifiers)) != len(identifiers):
        raise ValueError("spot plan ids must be unique")
    missing = {plan.symbol for plan in plans} - {bar.symbol for bar in bars}
    if missing:
        raise ValueError(f"missing bars for planned symbols: {sorted(missing)}")


def _process_exits(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
    invested: dict[str, float],
    proceeds: dict[str, float],
    trades: list[SpotTradeRecord],
) -> float:
    plan = position.plan
    if position.quantity <= 0.0:
        if bar.timestamp > plan.expires_at:
            position.closed_at = bar.timestamp
        return cash
    if bar.regime in plan.exit_regimes:
        return _close_position(
            config,
            position,
            bar.open,
            bar.timestamp,
            cash,
            SpotExitReason.REGIME,
            invested,
            proceeds,
            trades,
        )
    holding = plan.maximum_holding or config.maximum_holding
    if position.opened_at is not None and bar.timestamp - position.opened_at >= holding:
        return _close_position(
            config,
            position,
            bar.open,
            bar.timestamp,
            cash,
            SpotExitReason.TIME,
            invested,
            proceeds,
            trades,
        )
    if bar.low <= plan.protective_stop:
        return _close_position(
            config,
            position,
            plan.protective_stop,
            bar.timestamp,
            cash,
            SpotExitReason.STOP,
            invested,
            proceeds,
            trades,
        )
    return cash


def _fill_entries(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
    positions: dict[str, SpotPosition],
    latest: dict[str, float],
    invested: dict[str, float],
    bought_quantity: dict[str, float],
) -> float:
    plan = position.plan
    if bar.timestamp > plan.expires_at:
        return cash
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
        is_new = position.quantity <= 0.0
        if is_new and _open_positions(positions) >= config.maximum_concurrent_positions:
            continue
        target_cash = min(
            config.starting_cash * plan.allocation_pct / 100.0,
            config.starting_cash * config.maximum_allocation_per_position_pct / 100.0,
        )
        leg_cash = target_cash * entry.allocation_fraction
        reserve = config.starting_cash * config.minimum_cash_reserve_pct / 100.0
        exposure_room = _exposure_room(config, cash, positions, latest)
        leg_cash = min(leg_cash, max(0.0, cash - reserve), exposure_room)
        if leg_cash <= 0.0:
            continue
        fill_price = entry.price * (1.0 + config.slippage_pct / 100.0)
        fee = leg_cash * config.fee_pct / 100.0
        if leg_cash + fee > cash:
            continue
        quantity = leg_cash / fill_price
        position.quantity += quantity
        position.cost_basis += leg_cash
        position.entry_fees += fee
        position.filled_entry_indices.add(index)
        position.opened_at = position.opened_at or bar.timestamp
        invested[plan.plan_id] += leg_cash + fee
        bought_quantity[plan.plan_id] += quantity
        cash -= leg_cash + fee
    return cash


def _fill_targets(
    config: SpotBacktestConfig,
    position: SpotPosition,
    bar: SpotBar,
    cash: float,
    invested: dict[str, float],
    proceeds: dict[str, float],
    bought_quantity: dict[str, float],
    trades: list[SpotTradeRecord],
) -> float:
    if position.quantity <= 0.0:
        return cash
    plan_id = position.plan.plan_id
    for index, target in enumerate(position.plan.targets):
        if index in position.filled_target_indices or bar.high < target.price:
            continue
        quantity = min(position.quantity, bought_quantity[plan_id] * target.fraction)
        if quantity <= 0.0:
            continue
        fill = target.price * (1.0 - config.slippage_pct / 100.0)
        gross = quantity * fill
        fee = gross * config.fee_pct / 100.0
        basis = position.average_entry * quantity
        position.quantity -= quantity
        position.cost_basis = max(0.0, position.cost_basis - basis)
        position.realized_pnl += gross - fee - basis
        position.filled_target_indices.add(index)
        proceeds[plan_id] += gross - fee
        cash += gross - fee
    if position.quantity <= 1e-12:
        position.quantity = 0.0
        position.cost_basis = 0.0
        _record_closed(
            position,
            bar.timestamp,
            SpotExitReason.TARGET,
            invested,
            proceeds,
            trades,
        )
    return cash


def _close_position(
    config: SpotBacktestConfig,
    position: SpotPosition,
    price: float,
    timestamp: datetime,
    cash: float,
    reason: SpotExitReason,
    invested: dict[str, float],
    proceeds: dict[str, float],
    trades: list[SpotTradeRecord],
) -> float:
    fill = price * (1.0 - config.slippage_pct / 100.0)
    gross = position.quantity * fill
    fee = gross * config.fee_pct / 100.0
    plan_id = position.plan.plan_id
    proceeds[plan_id] += gross - fee
    position.realized_pnl += gross - fee - position.cost_basis
    position.quantity = 0.0
    position.cost_basis = 0.0
    cash += gross - fee
    _record_closed(position, timestamp, reason, invested, proceeds, trades)
    return cash


def _record_closed(
    position: SpotPosition,
    timestamp: datetime,
    reason: SpotExitReason,
    invested: dict[str, float],
    proceeds: dict[str, float],
    trades: list[SpotTradeRecord],
) -> None:
    position.closed_at = timestamp
    if position.opened_at is None:
        return
    plan_id = position.plan.plan_id
    capital = invested[plan_id]
    net = proceeds[plan_id] - capital
    trades.append(
        SpotTradeRecord(
            plan_id=plan_id,
            symbol=position.plan.symbol,
            strategy=position.plan.strategy,
            score_band=position.plan.score_band,
            market_regime=position.plan.market_regime.value,
            opened_at=position.opened_at,
            closed_at=timestamp,
            invested_cash=capital,
            proceeds=proceeds[plan_id],
            net_pnl=net,
            return_pct=net / capital * 100.0 if capital > 0.0 else 0.0,
            holding_duration_seconds=(timestamp - position.opened_at).total_seconds(),
            exit_reason=reason,
        )
    )


def _exposure_room(
    config: SpotBacktestConfig,
    cash: float,
    positions: dict[str, SpotPosition],
    latest: dict[str, float],
) -> float:
    market_value = _market_value(positions, latest)
    equity = cash + market_value
    cap = equity * config.maximum_total_exposure_pct / 100.0
    return max(0.0, cap - market_value)


def _market_value(positions: dict[str, SpotPosition], latest: dict[str, float]) -> float:
    return sum(
        position.quantity * latest.get(position.plan.symbol, position.average_entry)
        for position in positions.values()
        if position.quantity > 0.0
    )


def _open_positions(positions: dict[str, SpotPosition]) -> int:
    return sum(position.quantity > 0.0 for position in positions.values())


def _equity_point(
    timestamp: datetime,
    cash: float,
    positions: dict[str, SpotPosition],
    latest: dict[str, float],
) -> SpotEquityPoint:
    market_value = _market_value(positions, latest)
    equity = cash + market_value
    exposure = market_value / equity * 100.0 if equity > 0.0 else 0.0
    return SpotEquityPoint(
        timestamp=timestamp,
        cash=cash,
        market_value=market_value,
        equity=equity,
        exposure_pct=exposure,
        concurrent_positions=_open_positions(positions),
    )
