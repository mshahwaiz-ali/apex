"""Deterministic historical backtesting engine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace

from apex.backtesting.contracts import (
    BacktestActivationType,
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

    path_mfe_r = 0.0
    path_mae_r = 0.0
    for candle in candles[:max_candles]:
        favorable_r, adverse_r = _candle_excursions_r(
            signal,
            candle,
            signal.entry_price,
        )
        path_mfe_r = max(path_mfe_r, favorable_r)
        path_mae_r = max(path_mae_r, adverse_r)
    final_close = candles[max_candles - 1].close
    direction_correct = (
        final_close > signal.entry_price
        if signal.direction is TradeDirection.LONG
        else final_close < signal.entry_price
    )
    metadata = {
        **({} if metadata is None else dict(metadata)),
        "counterfactual_path_mfe_r": path_mfe_r,
        "counterfactual_path_mae_r": path_mae_r,
        "direction_correct_at_horizon": direction_correct,
    }

    activated = signal.activation_type is None
    entered = False
    next_target_index = 0
    remaining_quantity = signal.quantity
    gross = 0.0
    exit_fee_notional = 0.0
    maximum_favorable_excursion_r = 0.0
    maximum_adverse_excursion_r = 0.0
    for index, candle in enumerate(candles[:max_candles], start=1):
        if not activated:
            if _pre_entry_invalidated(signal, candle):
                return _unfilled_trade(
                    signal,
                    BacktestOutcome.PRE_ENTRY_INVALIDATED,
                    candle,
                    index,
                    metadata=metadata,
                    activation_outcome="pre_entry_invalidated",
                )
            if _maximum_chase_breached(signal, candle):
                return _unfilled_trade(
                    signal,
                    BacktestOutcome.MISSED_ENTRY,
                    candle,
                    index,
                    metadata=metadata,
                    activation_outcome="maximum_chase_breached",
                )
            if not _activation_triggered(signal, candle):
                if (
                    signal.activation_expiry_candles is not None
                    and index >= signal.activation_expiry_candles
                ):
                    return _unfilled_trade(
                        signal,
                        BacktestOutcome.ACTIVATION_EXPIRED,
                        candle,
                        index,
                        metadata=metadata,
                        activation_outcome="activation_expired",
                    )
                continue
            activated = True
            metadata = {
                **({} if metadata is None else dict(metadata)),
                "activation_outcome": "triggered",
                "activation_candle": index,
            }
            # Close-confirmed triggers become knowable only after this candle.
            # Begin entry-fill evaluation on the next candle to avoid lookahead.
            if signal.activation_type is not BacktestActivationType.PRICE_TOUCH:
                continue
        if not entered:
            entered = _entry_touched(signal, candle)
            if not entered:
                continue
        favorable_r, adverse_r = _candle_excursions_r(signal, candle, entry)
        maximum_favorable_excursion_r = max(maximum_favorable_excursion_r, favorable_r)
        maximum_adverse_excursion_r = max(maximum_adverse_excursion_r, adverse_r)
        runtime_metadata = _excursion_metadata(
            metadata,
            maximum_favorable_excursion_r,
            maximum_adverse_excursion_r,
        )
        stop_hit = _stop_hit(signal, candle, stop)
        hit_targets = _hit_target_indexes(signal, candle, targets, start=next_target_index)
        if stop_hit and hit_targets and config.conservative_intrabar:
            runtime_metadata = {
                **runtime_metadata,
                "same_candle_stop_target_ambiguous": True,
                "target_touched": True,
            }
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
                metadata=runtime_metadata,
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
                    metadata=runtime_metadata,
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
                metadata=runtime_metadata,
                partial_target_count=next_target_index,
            )

    final = candles[max_candles - 1]
    if not entered:
        return _unfilled_trade(
            signal,
            (BacktestOutcome.MISSED_ENTRY if activated else BacktestOutcome.ACTIVATION_EXPIRED),
            final,
            max_candles,
            metadata=metadata,
            activation_outcome=(
                "entry_not_touched_after_activation" if activated else "activation_window_ended"
            ),
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
        metadata=_excursion_metadata(
            metadata,
            maximum_favorable_excursion_r,
            maximum_adverse_excursion_r,
        ),
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
        report_metadata = dict(report.metadata)
        report_metadata.setdefault("methodology_version", request.methodology_version)
        report = replace(report, metadata=report_metadata)
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
    r_equity = 0.0
    r_peak = 0.0
    maximum_drawdown_r = 0.0
    for trade in trade_tuple:
        equity += trade.net_pnl
        peak = max(peak, equity)
        maximum_drawdown = max(maximum_drawdown, peak - equity)
        r_equity += trade.realized_r_multiple
        r_peak = max(r_peak, r_equity)
        maximum_drawdown_r = max(maximum_drawdown_r, r_peak - r_equity)
    r_profit = sum(max(0.0, trade.realized_r_multiple) for trade in trade_tuple)
    r_loss = abs(sum(min(0.0, trade.realized_r_multiple) for trade in trade_tuple))
    filled = tuple(trade for trade in trade_tuple if trade.metadata.get("entry_filled") is True)
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
            "entry_fill_count": len(filled),
            "entry_fill_rate": len(filled) / total if total else 0.0,
            "r_expectancy": (
                sum(trade.realized_r_multiple for trade in trade_tuple) / total if total else 0.0
            ),
            "r_profit_factor": None if r_loss == 0.0 else r_profit / r_loss,
            "maximum_drawdown_r": maximum_drawdown_r,
            "average_mfe_r": (
                sum(
                    float(trade.metadata.get("maximum_favorable_excursion_r", 0.0))
                    for trade in trade_tuple
                )
                / total
                if total
                else 0.0
            ),
            "average_mae_r": (
                sum(
                    float(trade.metadata.get("maximum_adverse_excursion_r", 0.0))
                    for trade in trade_tuple
                )
                / total
                if total
                else 0.0
            ),
            "tp1_touch_count": sum(
                trade.metadata.get("target_touched") is True for trade in trade_tuple
            ),
            "net_profitable_target_count": sum(
                trade.outcome is BacktestOutcome.TARGET and trade.net_pnl > 0.0
                for trade in trade_tuple
            ),
            "same_candle_stop_target_ambiguity_count": sum(
                trade.metadata.get("same_candle_stop_target_ambiguous") is True
                for trade in trade_tuple
            ),
        },
    )


def _entry_touched(signal: BacktestSignal, candle: Candle) -> bool:
    return candle.low <= signal.entry_price <= candle.high


def _activation_triggered(signal: BacktestSignal, candle: Candle) -> bool:
    kind = signal.activation_type
    level = signal.activation_level
    if kind is None:
        return True
    if level is None:
        return False
    if kind is BacktestActivationType.PRICE_TOUCH:
        return candle.low <= level <= candle.high
    if kind in {BacktestActivationType.CANDLE_CLOSE, BacktestActivationType.RECLAIM_CLOSE}:
        return (
            candle.close >= level
            if signal.direction is TradeDirection.LONG
            else candle.close <= level
        )
    if signal.direction is TradeDirection.LONG:
        return candle.low <= level and candle.close >= level
    return candle.high >= level and candle.close <= level


def _pre_entry_invalidated(signal: BacktestSignal, candle: Candle) -> bool:
    level = signal.pre_entry_invalidation_price
    if level is None:
        return False
    return candle.low <= level if signal.direction is TradeDirection.LONG else candle.high >= level


def _maximum_chase_breached(signal: BacktestSignal, candle: Candle) -> bool:
    level = signal.maximum_chase_price
    if level is None:
        return False
    return candle.high > level if signal.direction is TradeDirection.LONG else candle.low < level


def _unfilled_trade(
    signal: BacktestSignal,
    outcome: BacktestOutcome,
    candle: Candle,
    holding_candles: int,
    *,
    metadata: Mapping[str, str | int | float | bool] | None,
    activation_outcome: str,
) -> SimulatedTrade:
    output_metadata = _excursion_metadata(metadata, 0.0, 0.0)
    output_metadata["activation_outcome"] = activation_outcome
    output_metadata["partial_target_count"] = 0
    output_metadata["closed_percentage"] = 0.0
    output_metadata["entry_filled"] = False
    output_metadata["target_touched"] = False
    output_metadata["net_profitable_target"] = False
    output_metadata["entry_follow_through"] = (
        "moved_immediately_without_pullback"
        if activation_outcome == "maximum_chase_breached"
        else "entry_not_reached_before_expiry"
        if outcome is BacktestOutcome.ACTIVATION_EXPIRED
        else "invalidated_before_entry"
        if outcome is BacktestOutcome.PRE_ENTRY_INVALIDATED
        else "entry_zone_not_revisited"
    )
    return SimulatedTrade(
        signal=signal,
        outcome=outcome,
        exit_time=candle.close_time,
        exit_price=candle.close,
        gross_pnl=0.0,
        fees=0.0,
        net_pnl=0.0,
        realized_r_multiple=0.0,
        holding_candles=holding_candles,
        metadata=output_metadata,
    )


def _stop_hit(signal: BacktestSignal, candle: Candle, stop: float) -> bool:
    return candle.low <= stop if signal.direction is TradeDirection.LONG else candle.high >= stop


def _target_hit(signal: BacktestSignal, candle: Candle, target: float) -> bool:
    return (
        candle.high >= target if signal.direction is TradeDirection.LONG else candle.low <= target
    )


def _candle_excursions_r(
    signal: BacktestSignal,
    candle: Candle,
    entry: float,
) -> tuple[float, float]:
    risk_per_unit = abs(entry - signal.stop_price)
    if risk_per_unit <= 0.0:
        return 0.0, 0.0
    if signal.direction is TradeDirection.LONG:
        favorable = max(0.0, candle.high - entry)
        adverse = max(0.0, entry - candle.low)
    else:
        favorable = max(0.0, entry - candle.low)
        adverse = max(0.0, candle.high - entry)
    return favorable / risk_per_unit, adverse / risk_per_unit


def _excursion_metadata(
    metadata: Mapping[str, str | int | float | bool] | None,
    maximum_favorable_excursion_r: float,
    maximum_adverse_excursion_r: float,
) -> dict[str, str | int | float | bool]:
    result = {} if metadata is None else dict(metadata)
    result["maximum_favorable_excursion_r"] = maximum_favorable_excursion_r
    result["maximum_adverse_excursion_r"] = maximum_adverse_excursion_r
    return result


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
                "activation_type": (
                    None if signal.activation_type is None else signal.activation_type.value
                ),
                "activation_level": signal.activation_level,
                "pre_entry_invalidation_price": signal.pre_entry_invalidation_price,
                "maximum_chase_price": signal.maximum_chase_price,
                "activation_expiry_candles": signal.activation_expiry_candles,
                "candidate_id": signal.candidate_id,
                "replay_source": signal.replay_source,
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
    funding = entry * signal.quantity * config.funding_pct / 100.0
    net = gross - fees - funding
    output_metadata: dict[str, str | int | float | bool] = (
        {} if metadata is None else dict(metadata)
    )
    output_metadata.setdefault("partial_target_count", partial_target_count)
    output_metadata.setdefault(
        "closed_percentage",
        min(100.0, sum(signal.partial_close_percentages[:partial_target_count])),
    )
    output_metadata.setdefault("entry_filled", True)
    output_metadata.setdefault(
        "entry_follow_through",
        "direct_cmp_fill" if signal.activation_type is None else "conditional_entry_filled",
    )
    output_metadata.setdefault(
        "target_touched",
        partial_target_count > 0 or output_metadata.get("target_touched") is True,
    )
    output_metadata.setdefault(
        "net_profitable_target",
        outcome is BacktestOutcome.TARGET and net > 0.0,
    )
    output_metadata.setdefault("same_candle_stop_target_ambiguous", False)

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
    output_metadata.setdefault("actual_funding", funding)
    output_metadata.setdefault("actual_net_loss", max(0.0, -net))
    output_metadata.setdefault("realized_r", net / signal.risk_amount)
    output_metadata.setdefault("planned_entry_price", planned_entry)
    output_metadata.setdefault("modeled_entry_fill_price", modeled_entry)
    output_metadata.setdefault("planned_stop_price", planned_stop)
    output_metadata.setdefault("modeled_stop_fill_price", modeled_stop_exit)
    output_metadata.setdefault("configured_fee_pct", config.fee_pct)
    output_metadata.setdefault("configured_slippage_pct", config.slippage_pct)
    output_metadata.setdefault("configured_funding_pct", config.funding_pct)

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
