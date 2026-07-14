"""Deterministic evidence enrichment for simulated backtest trades."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace

from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestOutcome,
    BacktestSignal,
    SimulatedTrade,
)
from apex.backtesting.engine import simulate_trade
from apex.domain.models import Candle
from apex.strategies import TradeDirection


def simulate_trade_with_evidence(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    config: BacktestConfig | None = None,
    metadata: Mapping[str, str | int | float | bool] | None = None,
) -> SimulatedTrade:
    """Simulate one trade and attach auditable entry and excursion evidence.

    Entry time is the open timestamp of the first candle touching the requested
    entry. The executed entry price includes configured slippage. Excursions use
    complete post-entry candles before the terminal candle. The terminal candle
    is bounded to the executed exit price so the result does not assume a price
    path after the trade has already closed.
    """

    effective_config = config or BacktestConfig()
    trade = simulate_trade(signal, candles, config=effective_config, metadata=metadata)
    if trade.outcome is BacktestOutcome.MISSED_ENTRY:
        return trade

    entry_index = _entry_index(signal, candles, maximum_holding_candles=effective_config.maximum_holding_candles)
    if entry_index is None:
        raise ValueError("entered simulated trade is missing an entry-touch candle")
    entry_candle = candles[entry_index]
    executed_entry = _slipped_entry(signal, effective_config)
    mfe_r, mae_r = _excursions_in_r(
        signal,
        candles[entry_index:],
        executed_entry=executed_entry,
        exit_time=trade.exit_time,
        exit_price=trade.exit_price,
    )
    enriched = dict(trade.metadata)
    enriched.update(
        {
            "entry_time": entry_candle.open_time.isoformat(),
            "executed_entry_price": executed_entry,
            "maximum_favorable_excursion_r": mfe_r,
            "maximum_adverse_excursion_r": mae_r,
        }
    )
    return replace(trade, metadata=enriched)


def _entry_index(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    maximum_holding_candles: int,
) -> int | None:
    limit = min(len(candles), maximum_holding_candles)
    return next(
        (
            index
            for index, candle in enumerate(candles[:limit])
            if candle.low <= signal.entry_price <= candle.high
        ),
        None,
    )


def _excursions_in_r(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    executed_entry: float,
    exit_time: object,
    exit_price: float,
) -> tuple[float, float]:
    favorable_prices = [executed_entry]
    adverse_prices = [executed_entry]
    for candle in candles:
        if candle.close_time < exit_time:
            if signal.direction is TradeDirection.LONG:
                favorable_prices.append(candle.high)
                adverse_prices.append(candle.low)
            else:
                favorable_prices.append(candle.low)
                adverse_prices.append(candle.high)
            continue
        if candle.close_time == exit_time:
            favorable_prices.append(exit_price)
            adverse_prices.append(exit_price)
        break

    if signal.direction is TradeDirection.LONG:
        favorable_pnl = (max(favorable_prices) - executed_entry) * signal.quantity
        adverse_pnl = (min(adverse_prices) - executed_entry) * signal.quantity
    else:
        favorable_pnl = (executed_entry - min(favorable_prices)) * signal.quantity
        adverse_pnl = (executed_entry - max(adverse_prices)) * signal.quantity
    return max(0.0, favorable_pnl / signal.risk_amount), min(
        0.0, adverse_pnl / signal.risk_amount
    )


def _slipped_entry(signal: BacktestSignal, config: BacktestConfig) -> float:
    slippage = signal.entry_price * config.slippage_pct / 100.0
    return (
        signal.entry_price + slippage
        if signal.direction is TradeDirection.LONG
        else signal.entry_price - slippage
    )
