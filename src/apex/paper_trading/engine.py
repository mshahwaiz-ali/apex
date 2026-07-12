"""Deterministic Phase 9 paper-trading lifecycle engine."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from datetime import UTC, datetime
from typing import Any

from apex.backtesting import BacktestSignal, signal_from_setup
from apex.domain.models import Candle
from apex.paper_trading.contracts import (
    TERMINAL_STATES,
    PaperPerformance,
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
        elif current.state is PaperTradeState.ENTERED:
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
    target_hit = _target_hit(signal, candle)
    if stop_hit and target_hit:
        state = (
            PaperTradeState.STOPPED if config.conservative_intrabar else PaperTradeState.TARGET_HIT
        )
        exit_price = signal.stop_price if state is PaperTradeState.STOPPED else signal.target_price
        return _close(
            trade,
            state,
            candle,
            exit_price,
            "ambiguous intrabar resolution",
            config,
            held,
        )
    if stop_hit:
        return _close(
            trade,
            PaperTradeState.STOPPED,
            candle,
            signal.stop_price,
            "stop hit",
            config,
            held,
        )
    if target_hit:
        return _close(
            trade,
            PaperTradeState.TARGET_HIT,
            candle,
            signal.target_price,
            "target hit",
            config,
            held,
        )
    if held >= config.maximum_holding_candles:
        return _close(
            trade,
            PaperTradeState.EXPIRED,
            candle,
            candle.close,
            "maximum holding period reached",
            config,
            held,
        )
    return replace(trade, updated_at=candle.close_time, candles_held=held)


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
        gross = (
            (final_exit - entry_price) * trade.signal.quantity
            if trade.signal.direction is TradeDirection.LONG
            else (entry_price - final_exit) * trade.signal.quantity
        )
        fees = (entry_price + final_exit) * trade.signal.quantity * config.fee_pct / 100.0
        net_pnl = gross - fees
        realized_r = net_pnl / trade.signal.risk_amount
    return replace(
        trade,
        state=state,
        updated_at=candle.close_time,
        exit_time=candle.close_time,
        exit_price=final_exit,
        net_pnl=net_pnl,
        realized_r_multiple=realized_r,
        candles_waited=trade.candles_waited if candles_waited is None else candles_waited,
        candles_held=trade.candles_held if candles_held is None else candles_held,
        notes=(*trade.notes, note),
    )


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


def _target_hit(signal: BacktestSignal, candle: Candle) -> bool:
    return _target_hit_before_entry(signal, candle)


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


def _trade_id(symbol: str, generated_at: str, strategy: str) -> str:
    digest = hashlib.sha256(f"{symbol}|{generated_at}|{strategy}".encode()).hexdigest()
    return digest[:16]
