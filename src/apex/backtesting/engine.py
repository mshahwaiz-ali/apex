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

THESIS_PARTIAL_MOVE_R = 0.5
STOP_BREACH_SHALLOW_MAX_R = 0.25
STOP_BREACH_DEEP_MIN_R = 0.60
STOP_BREACH_DEEP_CLOSE_MIN_R = 0.35
STOP_BREACH_SHALLOW_RECLAIM_MAX_BARS = 2
STOP_BREACH_DEEP_RECLAIM_BARS = 4
STOP_BREACH_DEEP_CONSECUTIVE_CLOSES = 2


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
        **_thesis_outcome_metadata(signal, candles[:max_candles]),
        "counterfactual_path_mfe_r": path_mfe_r,
        "counterfactual_path_mae_r": path_mae_r,
        "direction_correct_at_horizon": direction_correct,
        "candidate_id": signal.candidate_id or "",
        "replay_source": signal.replay_source,
        "strategy_version": signal.strategy_version,
        "setup_methodology_version": signal.setup_methodology_version,
        "setup_validity": signal.setup_validity,
        "execution_authority": signal.execution_authority,
        "activation_required": signal.activation_type is not None,
        "activation_type": (
            "none" if signal.activation_type is None else signal.activation_type.value
        ),
        "activation_level": signal.activation_level or 0.0,
        "activation_expiry_candles": signal.activation_expiry_candles or 0,
        "stop_hit": False,
        "post_stop_classification": "no_stop_hit",
        "post_stop_followup_candles": 0,
        "post_stop_maximum_excursion_beyond_stop_r": 0.0,
        "post_stop_entry_reclaimed": False,
        "post_stop_bars_to_reclaim": 0,
        "post_stop_tp1_reached": False,
        "post_stop_maximum_favorable_excursion_r": 0.0,
        "post_stop_maximum_adverse_excursion_r": 0.0,
        "post_stop_adverse_close_beyond_stop": False,
    }

    activated = signal.activation_type is None
    entered = False
    next_target_index = 0
    remaining_quantity = signal.quantity
    gross = 0.0
    exit_fee_notional = 0.0
    maximum_favorable_excursion_r = 0.0
    maximum_adverse_excursion_r = 0.0
    first_stop_touch_candle: int | None = None
    first_stop_touch_time: str | None = None
    first_tp1_touch_candle: int | None = None
    first_tp1_touch_time: str | None = None
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
                "terminal_state": "activated",
                "activation_candle": index,
                "activation_time": candle.close_time.isoformat(),
                "activation_price": signal.activation_level or signal.entry_price,
            }
            # Close-confirmed triggers become knowable only after this candle.
            # Begin entry-fill evaluation on the next candle to avoid lookahead.
            if signal.activation_type is not BacktestActivationType.PRICE_TOUCH:
                continue
        if not entered:
            entered = _entry_touched(signal, candle)
            if not entered:
                continue
            metadata = {
                **({} if metadata is None else dict(metadata)),
                "entry_fill_candle": index,
                "entry_fill_time": candle.close_time.isoformat(),
                "entry_fill_price": entry,
                "activation_wait_candles": (
                    0
                    if signal.activation_type is None
                    else max(
                        0,
                        index - int(metadata.get("activation_candle", index)),
                    )
                ),
            }
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
        if stop_hit and first_stop_touch_candle is None:
            first_stop_touch_candle = index
            first_stop_touch_time = candle.close_time.isoformat()
        if hit_targets and first_tp1_touch_candle is None:
            first_tp1_touch_candle = index
            first_tp1_touch_time = candle.close_time.isoformat()
        runtime_metadata = {
            **runtime_metadata,
            "pre_exit_mfe_r": maximum_favorable_excursion_r,
            "pre_exit_mae_r": maximum_adverse_excursion_r,
            "first_stop_touch_candle": first_stop_touch_candle or 0,
            "first_stop_touch_time": first_stop_touch_time or "",
            "first_tp1_touch_candle": first_tp1_touch_candle or 0,
            "first_tp1_touch_time": first_tp1_touch_time or "",
        }
        if stop_hit and hit_targets and config.conservative_intrabar:
            runtime_metadata = {
                **runtime_metadata,
                "same_candle_stop_target_ambiguous": True,
                "target_touched": True,
                "first_exit_event": "same_candle_ambiguous_stop_first",
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
                metadata={
                    **runtime_metadata,
                    **_post_stop_thesis_metadata(
                        signal,
                        candles[index:max_candles],
                        entry=entry,
                        stop=stop,
                    ),
                },
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
                    metadata={
                        **runtime_metadata,
                        "first_exit_event": "target",
                    },
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
                metadata={
                    **runtime_metadata,
                    "first_exit_event": "stop",
                    **_post_stop_thesis_metadata(
                        signal,
                        candles[index:max_candles],
                        entry=entry,
                        stop=stop,
                    ),
                },
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
        metadata={
            **_excursion_metadata(
                metadata,
                maximum_favorable_excursion_r,
                maximum_adverse_excursion_r,
            ),
            "pre_exit_mfe_r": maximum_favorable_excursion_r,
            "pre_exit_mae_r": maximum_adverse_excursion_r,
            "first_stop_touch_candle": first_stop_touch_candle or 0,
            "first_stop_touch_time": first_stop_touch_time or "",
            "first_tp1_touch_candle": first_tp1_touch_candle or 0,
            "first_tp1_touch_time": first_tp1_touch_time or "",
            "first_exit_event": "expired",
        },
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
    output_metadata["terminal_state"] = (
        "pre_entry_invalidated"
        if outcome is BacktestOutcome.PRE_ENTRY_INVALIDATED
        else "missed_trigger"
        if outcome is BacktestOutcome.MISSED_ENTRY
        else "never_activated"
        if outcome is BacktestOutcome.ACTIVATION_EXPIRED
        else outcome.value
    )
    output_metadata["activation_wait_candles"] = holding_candles
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


def _thesis_outcome_metadata(
    signal: BacktestSignal,
    candles: Sequence[Candle],
) -> dict[str, str | int | float | bool]:
    """Evaluate the frozen directional thesis independently from entry execution.

    This diagnostic never changes activation, fill, stop, target, or production
    authority. The planned TP1 is the thesis objective. Pre-entry invalidation is
    preferred when available; otherwise the planned stop is the invalidation.
    Conservative same-candle ordering treats invalidation as occurring first.
    """

    invalidation = signal.pre_entry_invalidation_price or signal.stop_price
    risk_per_unit = abs(signal.entry_price - signal.stop_price)
    first_target_candle = 0
    first_invalidation_candle = 0
    maximum_favorable_r = 0.0
    late_reentry_candle = 0

    for index, candle in enumerate(candles, start=1):
        favorable_r, _ = _candle_excursions_r(signal, candle, signal.entry_price)
        maximum_favorable_r = max(maximum_favorable_r, favorable_r)

        if index > 1 and late_reentry_candle == 0 and _entry_touched(signal, candle):
            late_reentry_candle = index

        target_hit = _target_hit(signal, candle, signal.target_price)
        invalidation_hit = (
            candle.low <= invalidation
            if signal.direction is TradeDirection.LONG
            else candle.high >= invalidation
        )

        if invalidation_hit and first_invalidation_candle == 0:
            first_invalidation_candle = index
        if target_hit and first_target_candle == 0:
            first_target_candle = index

        if target_hit or invalidation_hit:
            break

    target_before_invalidation = first_target_candle > 0 and (
        first_invalidation_candle == 0 or first_target_candle < first_invalidation_candle
    )
    invalidation_before_target = first_invalidation_candle > 0 and (
        first_target_candle == 0 or first_invalidation_candle <= first_target_candle
    )
    partial_success = (
        not target_before_invalidation
        and not invalidation_before_target
        and risk_per_unit > 0.0
        and maximum_favorable_r >= THESIS_PARTIAL_MOVE_R
    )

    if target_before_invalidation:
        outcome = "thesis_correct"
    elif invalidation_before_target:
        outcome = "thesis_wrong"
    elif partial_success:
        outcome = "thesis_partially_correct"
    else:
        outcome = "thesis_unresolved"

    return {
        "thesis_outcome": outcome,
        "target_before_invalidation": target_before_invalidation,
        "invalidation_before_target": invalidation_before_target,
        "partial_directional_success": partial_success,
        "thesis_target_price": signal.target_price,
        "thesis_invalidation_price": invalidation,
        "thesis_evaluation_horizon_candles": len(candles),
        "thesis_first_target_candle": first_target_candle,
        "thesis_first_invalidation_candle": first_invalidation_candle,
        "thesis_maximum_favorable_excursion_r": maximum_favorable_r,
        "late_reentry_available": (late_reentry_candle > 0 and not invalidation_before_target),
        "late_reentry_first_candle": late_reentry_candle,
    }


def _post_stop_thesis_metadata(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    entry: float,
    stop: float,
) -> dict[str, str | int | float | bool]:
    """Classify post-stop behavior without retroactively forgiving deep failure.

    The stop candle itself is excluded by callers because intrabar ordering is
    unknowable. Later recovery is diagnostic only. A deep adverse breach keeps
    precedence over any subsequent reclaim or TP1 touch.
    """

    risk_per_unit = abs(entry - stop)
    if risk_per_unit <= 0.0:
        return {
            "stop_hit": True,
            "post_stop_classification": "ambiguous_after_stop",
            "post_stop_followup_candles": len(candles),
            "post_stop_maximum_excursion_beyond_stop_r": 0.0,
            "post_stop_maximum_close_beyond_stop_r": 0.0,
            "post_stop_bars_traded_beyond_stop": 0,
            "post_stop_bars_closed_beyond_stop": 0,
            "post_stop_max_consecutive_closes_beyond_stop": 0,
            "post_stop_entry_reclaimed": False,
            "post_stop_stop_reclaimed": False,
            "post_stop_bars_to_reclaim": 0,
            "post_stop_bars_to_stop_reclaim": 0,
            "post_stop_tp1_reached": False,
            "post_stop_maximum_favorable_excursion_r": 0.0,
            "post_stop_maximum_adverse_excursion_r": 0.0,
            "post_stop_adverse_close_beyond_stop": False,
            "shallow_stop_sweep": False,
            "moderate_stop_breach": False,
            "deep_directional_failure": False,
            "directional_failure_before_recovery": False,
            "later_recovery_after_directional_failure": False,
        }

    maximum_favorable_r = 0.0
    maximum_adverse_r = 0.0
    maximum_beyond_stop_r = 0.0
    maximum_close_beyond_stop_r = 0.0
    bars_traded_beyond_stop = 0
    bars_closed_beyond_stop = 0
    consecutive_closes_beyond_stop = 0
    maximum_consecutive_closes_beyond_stop = 0
    bars_to_entry_reclaim = 0
    bars_to_stop_reclaim = 0
    entry_reclaimed = False
    stop_reclaimed = False
    tp1_reached = False
    first_recovery_candle = 0

    for index, candle in enumerate(candles, start=1):
        favorable_r, adverse_r = _candle_excursions_r(signal, candle, entry)
        maximum_favorable_r = max(maximum_favorable_r, favorable_r)
        maximum_adverse_r = max(maximum_adverse_r, adverse_r)

        if signal.direction is TradeDirection.LONG:
            beyond_stop = max(0.0, stop - candle.low) / risk_per_unit
            close_beyond_stop = max(0.0, stop - candle.close) / risk_per_unit
            traded_beyond_stop = candle.low < stop
            closed_beyond_stop = candle.close < stop
            stop_reclaim = candle.close >= stop
            entry_reclaim = candle.high >= entry
        else:
            beyond_stop = max(0.0, candle.high - stop) / risk_per_unit
            close_beyond_stop = max(0.0, candle.close - stop) / risk_per_unit
            traded_beyond_stop = candle.high > stop
            closed_beyond_stop = candle.close > stop
            stop_reclaim = candle.close <= stop
            entry_reclaim = candle.low <= entry

        maximum_beyond_stop_r = max(maximum_beyond_stop_r, beyond_stop)
        maximum_close_beyond_stop_r = max(
            maximum_close_beyond_stop_r,
            close_beyond_stop,
        )
        if traded_beyond_stop:
            bars_traded_beyond_stop += 1
        if closed_beyond_stop:
            bars_closed_beyond_stop += 1
            consecutive_closes_beyond_stop += 1
            maximum_consecutive_closes_beyond_stop = max(
                maximum_consecutive_closes_beyond_stop,
                consecutive_closes_beyond_stop,
            )
        else:
            consecutive_closes_beyond_stop = 0

        if stop_reclaim and not stop_reclaimed:
            stop_reclaimed = True
            bars_to_stop_reclaim = index
            first_recovery_candle = index
        if entry_reclaim and not entry_reclaimed:
            entry_reclaimed = True
            bars_to_entry_reclaim = index
            if first_recovery_candle == 0:
                first_recovery_candle = index
        tp1_reached = tp1_reached or _target_hit(signal, candle, signal.target_price)

    adverse_close_beyond_stop = bars_closed_beyond_stop > 0
    deep_directional_failure = (
        maximum_beyond_stop_r >= STOP_BREACH_DEEP_MIN_R
        or maximum_close_beyond_stop_r >= STOP_BREACH_DEEP_CLOSE_MIN_R
        or maximum_consecutive_closes_beyond_stop >= STOP_BREACH_DEEP_CONSECUTIVE_CLOSES
        or (
            bars_traded_beyond_stop > 0
            and (not stop_reclaimed or bars_to_stop_reclaim > STOP_BREACH_DEEP_RECLAIM_BARS)
        )
    )
    shallow_stop_sweep = (
        not deep_directional_failure
        and maximum_beyond_stop_r <= STOP_BREACH_SHALLOW_MAX_R
        and bars_closed_beyond_stop <= 1
        and stop_reclaimed
        and 0 < bars_to_stop_reclaim <= STOP_BREACH_SHALLOW_RECLAIM_MAX_BARS
    )
    moderate_stop_breach = (
        not deep_directional_failure and not shallow_stop_sweep and maximum_beyond_stop_r > 0.0
    )
    later_recovery_after_directional_failure = deep_directional_failure and (
        entry_reclaimed or tp1_reached
    )

    if deep_directional_failure:
        classification = (
            "deep_directional_failure_then_recovery"
            if later_recovery_after_directional_failure
            else "deep_directional_failure"
        )
    elif shallow_stop_sweep and tp1_reached:
        classification = "shallow_stop_sweep_then_tp"
    elif shallow_stop_sweep:
        classification = "shallow_stop_sweep_then_recovery"
    elif moderate_stop_breach and (entry_reclaimed or tp1_reached):
        classification = "moderate_stop_breach_then_recovery"
    elif moderate_stop_breach:
        classification = "moderate_stop_breach"
    elif tp1_reached:
        classification = "recovery_without_material_stop_breach_then_tp"
    elif entry_reclaimed:
        classification = "recovery_without_material_stop_breach"
    else:
        classification = "ambiguous_after_stop"

    return {
        "stop_hit": True,
        "post_stop_classification": classification,
        "post_stop_followup_candles": len(candles),
        "post_stop_maximum_excursion_beyond_stop_r": maximum_beyond_stop_r,
        "post_stop_maximum_close_beyond_stop_r": maximum_close_beyond_stop_r,
        "post_stop_bars_traded_beyond_stop": bars_traded_beyond_stop,
        "post_stop_bars_closed_beyond_stop": bars_closed_beyond_stop,
        "post_stop_max_consecutive_closes_beyond_stop": (maximum_consecutive_closes_beyond_stop),
        "post_stop_entry_reclaimed": entry_reclaimed,
        "post_stop_stop_reclaimed": stop_reclaimed,
        "post_stop_bars_to_reclaim": bars_to_entry_reclaim,
        "post_stop_bars_to_stop_reclaim": bars_to_stop_reclaim,
        "post_stop_first_recovery_candle": first_recovery_candle,
        "post_stop_tp1_reached": tp1_reached,
        "post_stop_maximum_favorable_excursion_r": maximum_favorable_r,
        "post_stop_maximum_adverse_excursion_r": maximum_adverse_r,
        "post_stop_adverse_close_beyond_stop": adverse_close_beyond_stop,
        "shallow_stop_sweep": shallow_stop_sweep,
        "moderate_stop_breach": moderate_stop_breach,
        "deep_directional_failure": deep_directional_failure,
        "directional_failure_before_recovery": deep_directional_failure,
        "later_recovery_after_directional_failure": (later_recovery_after_directional_failure),
    }


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
                "strategy_version": signal.strategy_version,
                "setup_methodology_version": signal.setup_methodology_version,
                "setup_validity": signal.setup_validity,
                "execution_authority": signal.execution_authority,
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
    output_metadata.setdefault("terminal_state", outcome.value)
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
