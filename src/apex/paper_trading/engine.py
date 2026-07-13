"""Deterministic Phase 9 paper-trading lifecycle engine."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from apex.backtesting import BacktestReport, BacktestSignal, signal_from_setup
from apex.domain import (
    TradeLifecycle,
    TradeLifecycleEvent,
    TradeLifecycleEventType,
    replay_lifecycle_events,
)
from apex.domain.models import Candle
from apex.paper_trading.contracts import (
    TERMINAL_STATES,
    BacktestPaperComparison,
    PaperPerformance,
    PaperReport,
    PaperTrade,
    PaperTradeConfig,
    PaperTradeState,
)
from apex.risk.contracts import RiskApprovedSetup
from apex.strategies import TradeDirection


def create_paper_trade(
    setup: RiskApprovedSetup,
    *,
    analysis_payload: dict[str, Any],
    futures_plan: dict[str, Any] | None = None,
    created_at: datetime | None = None,
) -> PaperTrade:
    """Create an auditable paper trade from a risk-approved setup."""

    timestamp = created_at or datetime.now(UTC)
    signal = signal_from_setup(setup)
    trade_id = _trade_id(signal.symbol, signal.generated_at.isoformat(), signal.strategy.value)
    return PaperTrade(
        trade_id=trade_id,
        signal=signal,
        state=PaperTradeState.WAITING_FOR_ENTRY,
        created_at=timestamp,
        updated_at=timestamp,
        analysis_payload=analysis_payload,
        futures_plan=futures_plan,
        lifecycle_events=(
            _event(TradeLifecycleEventType.SETUP_GENERATED, timestamp),
            _event(TradeLifecycleEventType.WAITING_FOR_ENTRY, timestamp),
        ),
        notes=("paper trade generated from approved setup",),
    )


def update_paper_trade(
    trade: PaperTrade,
    candles: tuple[Candle, ...],
    *,
    config: PaperTradeConfig | None = None,
) -> PaperTrade:
    """Advance one paper trade with closed candles."""

    if config is None:
        config = PaperTradeConfig()
    if trade.state in TERMINAL_STATES:
        return trade
    if not candles:
        return trade

    current = trade
    for candle in candles:
        if current.state is PaperTradeState.WAITING_FOR_ENTRY:
            current = _update_waiting_trade(current, candle, config)
        elif current.state in {PaperTradeState.ENTERED, PaperTradeState.PARTIALLY_CLOSED}:
            current = _update_entered_trade(current, candle, config)
        if current.state in TERMINAL_STATES:
            return current
    return current


def summarize_paper_trades(trades: tuple[PaperTrade, ...]) -> PaperPerformance:
    """Calculate live paper performance from stored trades."""

    closed = tuple(trade for trade in trades if not trade.is_open)
    wins = tuple(trade for trade in closed if trade.net_pnl > 0.0)
    by_state: dict[str, int] = {}
    for trade in trades:
        by_state[trade.state.value] = by_state.get(trade.state.value, 0) + 1
    return PaperPerformance(
        total_trades=len(trades),
        open_trades=len(trades) - len(closed),
        closed_trades=len(closed),
        net_pnl=sum(trade.net_pnl for trade in closed),
        win_rate=len(wins) / len(closed) if closed else 0.0,
        average_r_multiple=(
            sum(trade.realized_r_multiple for trade in closed) / len(closed) if closed else 0.0
        ),
        by_state=by_state,
    )


def generate_paper_report(
    trades: tuple[PaperTrade, ...],
    *,
    period: str,
    generated_at: datetime | None = None,
) -> PaperReport:
    """Generate a period-scoped paper trading report from stored trades."""

    timestamp = generated_at or datetime.now(UTC)
    performance = summarize_paper_trades(trades)
    return PaperReport(
        period=period,
        generated_at=timestamp,
        performance=performance,
        notes=(
            f"closed_trades={performance.closed_trades}",
            f"open_trades={performance.open_trades}",
        ),
    )


def compare_backtest_to_paper(
    backtest: BacktestReport,
    paper: PaperPerformance,
    *,
    generated_at: datetime | None = None,
) -> BacktestPaperComparison:
    """Compare realized paper performance against a backtest report."""

    timestamp = generated_at or datetime.now(UTC)
    notes: list[str] = []
    if paper.total_trades != backtest.total_trades:
        notes.append("trade counts differ between backtest and paper sample")
    if paper.win_rate < backtest.win_rate:
        notes.append("paper win rate is below backtest win rate")
    return BacktestPaperComparison(
        generated_at=timestamp,
        backtest_total_trades=backtest.total_trades,
        paper_total_trades=paper.total_trades,
        net_pnl_delta=paper.net_pnl - backtest.net_profit,
        win_rate_delta=paper.win_rate - backtest.win_rate,
        average_r_delta=paper.average_r_multiple - backtest.average_risk_reward,
        notes=tuple(notes) or ("paper and backtest metrics compared",),
    )


def paper_lifecycle_snapshot(trade: PaperTrade) -> TradeLifecycle:
    """Replay stored paper lifecycle events into the canonical lifecycle snapshot."""

    events = tuple(
        TradeLifecycleEvent(
            event_type=TradeLifecycleEventType(str(event["event_type"])),
            occurred_at=datetime.fromisoformat(str(event["occurred_at"])),
            closed_percentage=event.get("closed_percentage"),
            stop_price=event.get("stop_price"),
            trailing_stop_price=event.get("trailing_stop_price"),
            target_label=event.get("target_label"),
            runner_active=event.get("runner_active"),
            reason=event.get("reason"),
        )
        for event in trade.lifecycle_events
    )
    return replay_lifecycle_events(created_at=trade.created_at, events=events)


def build_paper_replay_report(
    trades: tuple[PaperTrade, ...],
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    """Replay stored paper lifecycle events into a reproducible audit report."""

    timestamp = generated_at or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("paper replay report time must be timezone-aware")
    replayed: list[dict[str, Any]] = []
    failures: dict[str, str] = {}
    for trade in trades:
        try:
            snapshot = paper_lifecycle_snapshot(trade)
        except ValueError as exc:
            failures[trade.trade_id] = str(exc)
            continue
        replayed.append(
            {
                "trade_id": trade.trade_id,
                "symbol": trade.signal.symbol,
                "paper_state": trade.state.value,
                "lifecycle_state": snapshot.state.value,
                "created_at": snapshot.created_at.isoformat(),
                "updated_at": snapshot.updated_at.isoformat(),
                "entered_at": (
                    None if snapshot.entered_at is None else snapshot.entered_at.isoformat()
                ),
                "closed_at": (
                    None if snapshot.closed_at is None else snapshot.closed_at.isoformat()
                ),
                "closed_percentage": snapshot.closed_percentage,
                "active_stop_price": snapshot.active_stop_price,
                "trailing_stop_price": snapshot.trailing_stop_price,
                "runner_active": snapshot.runner_active,
                "partial_targets_hit": list(snapshot.partial_targets_hit),
                "last_target_label": snapshot.last_target_label,
                "event_count": len(trade.lifecycle_events),
                "reason": snapshot.reason,
            }
        )
    return {
        "schema_version": 1,
        "generated_at": timestamp.isoformat(),
        "trade_count": len(trades),
        "replayed_count": len(replayed),
        "failure_count": len(failures),
        "trades": replayed,
        "failures": failures,
    }


def _update_waiting_trade(
    trade: PaperTrade,
    candle: Candle,
    config: PaperTradeConfig,
) -> PaperTrade:
    signal = trade.signal
    waited = trade.candles_waited + 1
    if _target_hit_before_entry(signal, candle):
        return _close(
            trade,
            PaperTradeState.EXPIRED,
            candle,
            signal.target_price,
            "target reached before entry",
            config,
            candles_waited=waited,
        )
    if _stop_violated_before_entry(signal, candle):
        return _close(
            trade,
            PaperTradeState.INVALIDATED,
            candle,
            signal.stop_price,
            "stop violated before entry",
            config,
            candles_waited=waited,
        )
    if _entry_touched(signal, candle):
        entry = _slipped_entry(signal, config)
        return replace(
            trade,
            state=PaperTradeState.ENTERED,
            updated_at=candle.close_time,
            entry_time=candle.close_time,
            entry_price=entry,
            candles_waited=waited,
            lifecycle_events=(
                *trade.lifecycle_events,
                _event(TradeLifecycleEventType.ENTRY_FILLED, candle.close_time),
            ),
            notes=(*trade.notes, "entry filled"),
        )
    if waited >= config.entry_timeout_candles:
        return _close(
            trade,
            PaperTradeState.EXPIRED,
            candle,
            candle.close,
            "entry timeout reached",
            config,
            candles_waited=waited,
        )
    return replace(trade, updated_at=candle.close_time, candles_waited=waited)


def _update_entered_trade(
    trade: PaperTrade,
    candle: Candle,
    config: PaperTradeConfig,
) -> PaperTrade:
    signal = trade.signal
    held = trade.candles_held + 1
    stop_hit = _stop_hit(signal, candle)
    hit_targets = _hit_target_indexes(signal, candle, start=trade.partial_target_count)
    if stop_hit and hit_targets and config.conservative_intrabar:
        return _close(
            trade,
            PaperTradeState.STOPPED,
            candle,
            signal.stop_price,
            "ambiguous intrabar resolution",
            config,
            held,
        )
    current = trade
    for target_index in hit_targets:
        current = _apply_target_fill(current, candle, target_index, config, held)
        if current.state is PaperTradeState.TARGET_HIT:
            return current
    if stop_hit:
        return _close(
            current,
            PaperTradeState.STOPPED,
            candle,
            signal.stop_price,
            "stop hit",
            config,
            held,
        )
    if held >= config.maximum_holding_candles:
        return _close(
            current,
            PaperTradeState.EXPIRED,
            candle,
            candle.close,
            "maximum holding period reached",
            config,
            held,
        )
    return replace(current, updated_at=candle.close_time, candles_held=held)


def _apply_target_fill(
    trade: PaperTrade,
    candle: Candle,
    target_index: int,
    config: PaperTradeConfig,
    candles_held: int,
) -> PaperTrade:
    entry_price = trade.entry_price
    if entry_price is None:
        return trade
    signal = trade.signal
    target_price = _slipped_exit(signal, signal.target_prices[target_index], config)
    partial = signal.partial_close_percentages[target_index]
    fill_quantity = signal.quantity * partial / 100.0
    gross = _gross_for_fill(
        signal,
        entry=entry_price,
        exit_price=target_price,
        quantity=fill_quantity,
    )
    fees = (entry_price + target_price) * fill_quantity * config.fee_pct / 100.0
    net_pnl = trade.net_pnl + gross - fees
    target_count = target_index + 1
    closed_percentage = min(100.0, sum(signal.partial_close_percentages[:target_count]))
    terminal = closed_percentage >= 100.0
    state = PaperTradeState.TARGET_HIT if terminal else PaperTradeState.PARTIALLY_CLOSED
    event_type = (
        TradeLifecycleEventType.FULL_TARGET_HIT
        if terminal
        else TradeLifecycleEventType.PARTIAL_TARGET_HIT
    )
    return replace(
        trade,
        state=state,
        updated_at=candle.close_time,
        exit_time=candle.close_time if terminal else trade.exit_time,
        exit_price=target_price,
        net_pnl=net_pnl,
        realized_r_multiple=net_pnl / signal.risk_amount,
        partial_target_count=target_count,
        closed_percentage=closed_percentage,
        candles_held=candles_held,
        lifecycle_events=(
            *trade.lifecycle_events,
            _event(
                event_type,
                candle.close_time,
                reason=f"target {target_count} hit",
                closed_percentage=closed_percentage,
                target_label=f"tp{target_count}",
            ),
        ),
        notes=(*trade.notes, f"target {target_count} hit"),
    )


def _close(
    trade: PaperTrade,
    state: PaperTradeState,
    candle: Candle,
    exit_price: float,
    note: str,
    config: PaperTradeConfig,
    candles_held: int | None = None,
    *,
    candles_waited: int | None = None,
) -> PaperTrade:
    entry_price = trade.entry_price
    net_pnl = 0.0
    realized_r = 0.0
    final_exit = exit_price
    pnl_states = {
        PaperTradeState.STOPPED,
        PaperTradeState.TARGET_HIT,
        PaperTradeState.EXPIRED,
    }
    if entry_price is not None and state in pnl_states:
        final_exit = _slipped_exit(trade.signal, exit_price, config)
        remaining_quantity = trade.signal.quantity * (100.0 - trade.closed_percentage) / 100.0
        gross = (
            (final_exit - entry_price) * remaining_quantity
            if trade.signal.direction is TradeDirection.LONG
            else (entry_price - final_exit) * remaining_quantity
        )
        fees = (entry_price + final_exit) * remaining_quantity * config.fee_pct / 100.0
        net_pnl = trade.net_pnl + gross - fees
        realized_r = net_pnl / trade.signal.risk_amount
    return replace(
        trade,
        state=state,
        updated_at=candle.close_time,
        exit_time=candle.close_time,
        exit_price=final_exit,
        net_pnl=net_pnl,
        realized_r_multiple=realized_r,
        closed_percentage=100.0 if entry_price is not None and state in pnl_states else 0.0,
        candles_waited=trade.candles_waited if candles_waited is None else candles_waited,
        candles_held=trade.candles_held if candles_held is None else candles_held,
        lifecycle_events=(
            *trade.lifecycle_events,
            _event(_paper_state_event_type(state), candle.close_time, reason=note),
        ),
        notes=(*trade.notes, note),
    )


def _paper_state_event_type(state: PaperTradeState) -> TradeLifecycleEventType:
    if state is PaperTradeState.TARGET_HIT:
        return TradeLifecycleEventType.FULL_TARGET_HIT
    if state is PaperTradeState.STOPPED:
        return TradeLifecycleEventType.STOPPED_OUT
    if state is PaperTradeState.INVALIDATED:
        return TradeLifecycleEventType.STRUCTURAL_INVALIDATION
    if state is PaperTradeState.CANCELLED:
        return TradeLifecycleEventType.CANCELLED
    return TradeLifecycleEventType.EXPIRED


def _event(
    event_type: TradeLifecycleEventType,
    occurred_at: datetime,
    *,
    reason: str | None = None,
    closed_percentage: float | None = None,
    target_label: str | None = None,
) -> dict[str, Any]:
    return {
        "event_type": event_type.value,
        "occurred_at": occurred_at.isoformat(),
        "closed_percentage": closed_percentage,
        "target_label": target_label,
        "reason": reason,
    }


def _entry_touched(signal: BacktestSignal, candle: Candle) -> bool:
    return candle.low <= signal.entry_price <= candle.high


def _stop_violated_before_entry(signal: BacktestSignal, candle: Candle) -> bool:
    return (
        candle.low <= signal.stop_price
        if signal.direction is TradeDirection.LONG
        else candle.high >= signal.stop_price
    )


def _target_hit_before_entry(signal: BacktestSignal, candle: Candle) -> bool:
    return (
        candle.high >= signal.target_price
        if signal.direction is TradeDirection.LONG
        else candle.low <= signal.target_price
    )


def _stop_hit(signal: BacktestSignal, candle: Candle) -> bool:
    return _stop_violated_before_entry(signal, candle)


def _hit_target_indexes(
    signal: BacktestSignal,
    candle: Candle,
    *,
    start: int,
) -> tuple[int, ...]:
    indexes: list[int] = []
    for index, target in enumerate(signal.target_prices[start:], start=start):
        if (
            candle.high >= target
            if signal.direction is TradeDirection.LONG
            else candle.low <= target
        ):
            indexes.append(index)
        else:
            break
    return tuple(indexes)


def _slipped_entry(signal: BacktestSignal, config: PaperTradeConfig) -> float:
    slippage = signal.entry_price * config.slippage_pct / 100.0
    return (
        signal.entry_price + slippage
        if signal.direction is TradeDirection.LONG
        else signal.entry_price - slippage
    )


def _slipped_exit(signal: BacktestSignal, price: float, config: PaperTradeConfig) -> float:
    slippage = price * config.slippage_pct / 100.0
    return price - slippage if signal.direction is TradeDirection.LONG else price + slippage


def _gross_for_fill(
    signal: BacktestSignal,
    *,
    entry: float,
    exit_price: float,
    quantity: float,
) -> float:
    return (
        (exit_price - entry) * quantity
        if signal.direction is TradeDirection.LONG
        else (entry - exit_price) * quantity
    )


def _trade_id(symbol: str, generated_at: str, strategy: str) -> str:
    digest = hashlib.sha256(f"{symbol}|{generated_at}|{strategy}".encode()).hexdigest()
    return digest[:16]
