"""Deterministic historical backtesting engine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict

from apex.backtesting.contracts import (
    BacktestConfig,
    BacktestOutcome,
    BacktestReport,
    BacktestRequest,
    BacktestSignal,
    BacktestStudy,
    SimulatedTrade,
)
from apex.domain.models import Candle
from apex.strategies import TradeDirection


def simulate_trade(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    config: BacktestConfig | None = None,
    metadata: Mapping[str, str | int | float | bool] | None = None,
) -> SimulatedTrade:
    """Replay one signal over future candles without assuming profitable ambiguity."""

    if config is None:
        config = BacktestConfig()
    if not candles:
        raise ValueError("simulation requires future candles")
    entry = _slipped_entry(signal, config)
    stop = signal.stop_price
    targets = signal.target_prices
    partials = signal.partial_close_percentages
    max_candles = min(len(candles), config.maximum_holding_candles)

    entered = False
    next_target_index = 0
    remaining_quantity = signal.quantity
    gross = 0.0
    exit_fee_notional = 0.0
    for index, candle in enumerate(candles[:max_candles], start=1):
        if not entered:
            entered = _entry_touched(signal, candle)
            if not entered:
                continue
        stop_hit = _stop_hit(signal, candle, stop)
        hit_targets = _hit_target_indexes(signal, candle, targets, start=next_target_index)
        if stop_hit and hit_targets and config.conservative_intrabar:
            return _trade_from_components(
                signal,
                BacktestOutcome.STOP,
                candle,
                index,
                entry,
                _slipped_exit(signal, stop, config),
                gross
                + _gross_for_fill(
                    signal,
                    entry=entry,
                    exit_price=_slipped_exit(signal, stop, config),
                    quantity=remaining_quantity,
                ),
                exit_fee_notional + _slipped_exit(signal, stop, config) * remaining_quantity,
                config,
                metadata=metadata,
                partial_target_count=next_target_index,
            )

        for target_index in hit_targets:
            target_price = _slipped_exit(signal, targets[target_index], config)
            fill_quantity = signal.quantity * partials[target_index] / 100.0
            fill_quantity = min(fill_quantity, remaining_quantity)
            gross += _gross_for_fill(
                signal,
                entry=entry,
                exit_price=target_price,
                quantity=fill_quantity,
            )
            exit_fee_notional += target_price * fill_quantity
            remaining_quantity -= fill_quantity
            next_target_index = target_index + 1
            if remaining_quantity <= 1e-12:
                return _trade_from_components(
                    signal,
                    BacktestOutcome.TARGET,
                    candle,
                    index,
                    entry,
                    target_price,
                    gross,
                    exit_fee_notional,
                    config,
                    metadata=metadata,
                    partial_target_count=next_target_index,
                )

        if stop_hit:
            stop_exit = _slipped_exit(signal, stop, config)
            return _trade_from_components(
                signal,
                BacktestOutcome.STOP,
                candle,
                index,
                entry,
                stop_exit,
                gross
                + _gross_for_fill(
                    signal,
                    entry=entry,
                    exit_price=stop_exit,
                    quantity=remaining_quantity,
                ),
                exit_fee_notional + stop_exit * remaining_quantity,
                config,
                metadata=metadata,
                partial_target_count=next_target_index,
            )

    final = candles[max_candles - 1]
    if not entered:
        return SimulatedTrade(
            signal=signal,
            outcome=BacktestOutcome.MISSED_ENTRY,
            exit_time=final.close_time,
            exit_price=final.close,
            gross_pnl=0.0,
            fees=0.0,
            net_pnl=0.0,
            realized_r_multiple=0.0,
            holding_candles=max_candles,
            metadata={} if metadata is None else metadata,
        )
    final_exit = _slipped_exit(signal, final.close, config)
    return _trade_from_components(
        signal,
        BacktestOutcome.EXPIRED,
        final,
        max_candles,
        entry,
        final_exit,
        gross
        + _gross_for_fill(
            signal,
            entry=entry,
            exit_price=final_exit,
            quantity=remaining_quantity,
        ),
        exit_fee_notional + final_exit * remaining_quantity,
        config,
        metadata=metadata,
        partial_target_count=next_target_index,
    )


class HistoricalBacktestRunner:
    """Run a deterministic chronological study from precomputed signals."""

    def run(self, request: BacktestRequest) -> BacktestStudy:
        trades: list[SimulatedTrade] = []
        skipped = 0
        for signal in request.signals:
            future = _future_candles(request, signal)
            if not future:
                skipped += 1
                continue
            trades.append(simulate_trade(signal, future, config=request.config))

        report = summarize_trades(trades)
        return BacktestStudy(
            request=request,
            report=report,
            dataset_hash=_dataset_hash(request),
            config_hash=_config_hash(request.config),
            code_hash=_hash_json({"code_version": request.code_version}),
            generated_signal_count=len(request.signals),
            simulated_trade_count=len(trades),
            skipped_signal_count=skipped,
        )


def summarize_trades(trades: Sequence[SimulatedTrade]) -> BacktestReport:
    """Aggregate deterministic backtest metrics."""

    trade_tuple = tuple(trades)
    wins = tuple(trade for trade in trade_tuple if trade.net_pnl > 0.0)
    losses = tuple(trade for trade in trade_tuple if trade.net_pnl < 0.0)
    breakeven = tuple(trade for trade in trade_tuple if trade.net_pnl == 0.0)
    total = len(trade_tuple)
    gross_profit = sum(trade.net_pnl for trade in wins)
    gross_loss = abs(sum(trade.net_pnl for trade in losses))
    net_profit = sum(trade.net_pnl for trade in trade_tuple)
    equity = 0.0
    peak = 0.0
    maximum_drawdown = 0.0
    for trade in trade_tuple:
        equity += trade.net_pnl
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, peak - equity)
    return BacktestReport(
        trades=trade_tuple,
        total_trades=total,
        win_rate=len(wins) / total if total else 0.0,
        loss_rate=len(losses) / total if total else 0.0,
        breakeven_rate=len(breakeven) / total if total else 0.0,
        gross_profit=gross_profit,
        gross_loss=gross_loss,
        net_profit=net_profit,
        profit_factor=None if gross_loss == 0.0 else gross_profit / gross_loss,
        average_win=gross_profit / len(wins) if wins else 0.0,
        average_loss=-(gross_loss / len(losses)) if losses else 0.0,
        average_risk_reward=(
            sum(trade.realized_r_multiple for trade in trade_tuple) / total if total else 0.0
        ),
        expectancy=net_profit / total if total else 0.0,
        maximum_drawdown=maximum_drawdown,
        consecutive_wins=_max_streak(trade_tuple, profitable=True),
        consecutive_losses=_max_streak(trade_tuple, profitable=False),
        by_symbol=_count_by_symbol(trade_tuple),
        by_strategy=_count_by_strategy(trade_tuple),
        metadata={
            "total_stop_outs": sum(trade.outcome is BacktestOutcome.STOP for trade in trade_tuple),
            "total_targets": sum(trade.outcome is BacktestOutcome.TARGET for trade in trade_tuple),
            "total_missed_entries": sum(
                trade.outcome is BacktestOutcome.MISSED_ENTRY for trade in trade_tuple
            ),
            "total_expired": sum(trade.outcome is BacktestOutcome.EXPIRED for trade in trade_tuple),
        },
    )


def _entry_touched(signal: BacktestSignal, candle: Candle) -> bool:
    return candle.low <= signal.entry_price <= candle.high


def _stop_hit(signal: BacktestSignal, candle: Candle, stop: float) -> bool:
    return candle.low <= stop if signal.direction is TradeDirection.LONG else candle.high >= stop


def _target_hit(signal: BacktestSignal, candle: Candle, target: float) -> bool:
    return (
        candle.high >= target if signal.direction is TradeDirection.LONG else candle.low <= target
    )


def _hit_target_indexes(
    signal: BacktestSignal,
    candle: Candle,
    targets: Sequence[float],
    *,
    start: int,
) -> tuple[int, ...]:
    indexes: list[int] = []
    for index, target in enumerate(targets[start:], start=start):
        if _target_hit(signal, candle, target):
            indexes.append(index)
        else:
            break
    return tuple(indexes)


def _future_candles(
    request: BacktestRequest,
    signal: BacktestSignal,
) -> tuple[Candle, ...]:
    candles = request.candles_by_symbol.get(signal.symbol, ())
    return tuple(
        candle for candle in candles if candle.open_time >= signal.generated_at and candle.is_closed
    )


def _dataset_hash(request: BacktestRequest) -> str:
    payload = {
        "dataset_id": request.dataset_id,
        "signals": [
            {
                "symbol": signal.symbol,
                "strategy": signal.strategy.value,
                "direction": signal.direction.value,
                "generated_at": signal.generated_at.isoformat(),
                "entry_price": signal.entry_price,
                "stop_price": signal.stop_price,
                "target_price": signal.target_price,
                "target_prices": list(signal.target_prices),
                "partial_close_percentages": list(signal.partial_close_percentages),
                "quantity": signal.quantity,
                "risk_amount": signal.risk_amount,
                "confidence_score": signal.confidence_score,
            }
            for signal in request.signals
        ],
        "candles": {
            symbol: [
                {
                    "open_time": candle.open_time.isoformat(),
                    "close_time": candle.close_time.isoformat(),
                    "open": candle.open,
                    "high": candle.high,
                    "low": candle.low,
                    "close": candle.close,
                    "volume": candle.volume,
                    "is_closed": candle.is_closed,
                    "source": candle.source,
                    "timeframe": candle.timeframe,
                }
                for candle in candles
            ]
            for symbol, candles in sorted(request.candles_by_symbol.items())
        },
    }
    return _hash_json(payload)


def _config_hash(config: BacktestConfig) -> str:
    return _hash_json(asdict(config))


def _hash_json(payload: object) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _slipped_entry(signal: BacktestSignal, config: BacktestConfig) -> float:
    slippage = signal.entry_price * config.slippage_pct / 100.0
    return (
        signal.entry_price + slippage
        if signal.direction is TradeDirection.LONG
        else signal.entry_price - slippage
    )


def _slipped_exit(signal: BacktestSignal, price: float, config: BacktestConfig) -> float:
    slippage = price * config.slippage_pct / 100.0
    return price - slippage if signal.direction is TradeDirection.LONG else price + slippage


def _trade(
    signal: BacktestSignal,
    outcome: BacktestOutcome,
    candle: Candle,
    holding_candles: int,
    entry: float,
    exit_price: float,
    config: BacktestConfig,
    metadata: Mapping[str, str | int | float | bool] | None = None,
) -> SimulatedTrade:
    exit_with_slippage = _slipped_exit(signal, exit_price, config)
    gross = _gross_for_fill(
        signal,
        entry=entry,
        exit_price=exit_with_slippage,
        quantity=signal.quantity,
    )
    return _trade_from_components(
        signal,
        outcome,
        candle,
        holding_candles,
        entry,
        exit_with_slippage,
        gross,
        exit_with_slippage * signal.quantity,
        config,
        metadata=metadata,
        partial_target_count=1 if outcome is BacktestOutcome.TARGET else 0,
    )


def _trade_from_components(
    signal: BacktestSignal,
    outcome: BacktestOutcome,
    candle: Candle,
    holding_candles: int,
    entry: float,
    exit_price: float,
    gross: float,
    exit_fee_notional: float,
    config: BacktestConfig,
    metadata: Mapping[str, str | int | float | bool] | None = None,
    *,
    partial_target_count: int = 0,
) -> SimulatedTrade:
    fees = (entry * signal.quantity + exit_fee_notional) * config.fee_pct / 100.0
    net = gross - fees
    output_metadata: dict[str, str | int | float | bool] = (
        {} if metadata is None else dict(metadata)
    )
    output_metadata.setdefault("partial_target_count", partial_target_count)
    output_metadata.setdefault(
        "closed_percentage",
        min(100.0, sum(signal.partial_close_percentages[:partial_target_count])),
    )

    planned_entry = signal.entry_price
    planned_stop = signal.stop_price
    modeled_entry = _slipped_entry(signal, config)
    modeled_stop_exit = _slipped_exit(signal, planned_stop, config)

    planned_stop_gross_pnl = _gross_for_fill(
        signal,
        entry=planned_entry,
        exit_price=planned_stop,
        quantity=signal.quantity,
    )
    modeled_stop_gross_pnl = _gross_for_fill(
        signal,
        entry=modeled_entry,
        exit_price=modeled_stop_exit,
        quantity=signal.quantity,
    )

    planned_entry_fee = modeled_entry * signal.quantity * config.fee_pct / 100.0
    planned_stop_exit_fee = modeled_stop_exit * signal.quantity * config.fee_pct / 100.0
    modeled_slippage_loss = max(
        0.0,
        planned_stop_gross_pnl - modeled_stop_gross_pnl,
    )
    expected_total_loss_at_stop = max(
        0.0,
        -(modeled_stop_gross_pnl - planned_entry_fee - planned_stop_exit_fee),
    )

    output_metadata.setdefault("configured_signal_risk_amount", signal.risk_amount)
    output_metadata.setdefault(
        "gross_stop_loss_at_planned_stop",
        max(0.0, -planned_stop_gross_pnl),
    )
    output_metadata.setdefault("entry_fee", planned_entry_fee)
    output_metadata.setdefault("planned_stop_exit_fee", planned_stop_exit_fee)
    output_metadata.setdefault("modeled_slippage_loss", modeled_slippage_loss)
    output_metadata.setdefault(
        "expected_total_loss_at_stop",
        expected_total_loss_at_stop,
    )
    output_metadata.setdefault("expected_r", -expected_total_loss_at_stop / signal.risk_amount)
    output_metadata.setdefault("actual_simulated_fill_loss", max(0.0, -gross))
    output_metadata.setdefault("actual_fees", fees)
    output_metadata.setdefault("actual_net_loss", max(0.0, -net))
    output_metadata.setdefault("realized_r", net / signal.risk_amount)
    output_metadata.setdefault("planned_entry_price", planned_entry)
    output_metadata.setdefault("modeled_entry_fill_price", modeled_entry)
    output_metadata.setdefault("planned_stop_price", planned_stop)
    output_metadata.setdefault("modeled_stop_fill_price", modeled_stop_exit)
    output_metadata.setdefault("configured_fee_pct", config.fee_pct)
    output_metadata.setdefault("configured_slippage_pct", config.slippage_pct)

    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=candle.close_time,
        exit_price=exit_price,
        gross_pnl=gross,
        fees=fees,
        net_pnl=net,
        realized_r_multiple=net / signal.risk_amount,
        holding_candles=holding_candles,
        metadata=output_metadata,
    )


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


def _max_streak(trades: Sequence[SimulatedTrade], *, profitable: bool) -> int:
    longest = 0
    current = 0
    for trade in trades:
        matches = trade.net_pnl > 0.0 if profitable else trade.net_pnl < 0.0
        current = current + 1 if matches else 0
        longest = max(longest, current)
    return longest


def _count_by_symbol(trades: Sequence[SimulatedTrade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        counts[trade.signal.symbol] = counts.get(trade.signal.symbol, 0) + 1
    return counts


def _count_by_strategy(trades: Sequence[SimulatedTrade]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        strategy = trade.signal.strategy.value
        counts[strategy] = counts.get(strategy, 0) + 1
    return counts
