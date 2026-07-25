"""Deterministic historical backtesting engine."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, replace
from datetime import datetime

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
from apex.backtesting.sweep_reclaim_adapter import (
    assess_post_stop_sweep_reclaim,
    sweep_reclaim_metadata,
)
from apex.domain.decision_features import decision_feature_snapshot
from apex.domain.deep_failure_risk import deep_failure_shadow_metadata
from apex.domain.models import Candle
from apex.domain.volatility_risk import volatility_risk_shadow_metadata
from apex.strategies import TradeDirection

THESIS_PARTIAL_MOVE_R = 0.5
STOP_BREACH_SHALLOW_MAX_R = 0.25
STOP_BREACH_DEEP_MIN_R = 0.60
STOP_BREACH_DEEP_CLOSE_MIN_R = 0.35
STOP_BREACH_SHALLOW_RECLAIM_MAX_BARS = 2
STOP_BREACH_DEEP_RECLAIM_BARS = 4
STOP_BREACH_DEEP_CONSECUTIVE_CLOSES = 2
SWEEP_RECLAIM_BODY_RATIO_MIN = 0.40
SWEEP_RECLAIM_CLOSE_LOCATION_MIN = 0.65
SWEEP_RECLAIM_MAX_CONFIRM_BARS = 2
SWEEP_RECLAIM_MIN_REMAINING_TARGET_R = 1.00
RECOVERY_MINIMUM_NET_R_GATE = 0.30
RECOVERY_MARKET_EPISODE_MINUTES = 30


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
    entry: float | None = None
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
        **deep_failure_shadow_metadata(signal),
        **_thesis_outcome_metadata(signal, candles[:max_candles]),
        **decision_feature_snapshot(signal),
        **volatility_risk_shadow_metadata(signal),
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
            if signal.activation_type is not None and _pre_entry_invalidated(
                signal,
                candle,
            ):
                return _unfilled_trade(
                    signal,
                    BacktestOutcome.PRE_ENTRY_INVALIDATED,
                    candle,
                    index,
                    metadata=metadata,
                    activation_outcome="pre_entry_invalidated_after_activation",
                )
            raw_entry = _entry_zone_fill_price(signal, candle)
            if raw_entry is None:
                if signal.activation_type is not None and _maximum_chase_breached(signal, candle):
                    return _unfilled_trade(
                        signal,
                        BacktestOutcome.MISSED_ENTRY,
                        candle,
                        index,
                        metadata=metadata,
                        activation_outcome="maximum_chase_breached_after_activation",
                    )
                continue
            signal = replace(
                signal,
                entry_price=raw_entry,
                risk_amount=abs(raw_entry - stop),
            )
            entry = _slipped_entry(signal, config)
            entered = True
            metadata = {
                **({} if metadata is None else dict(metadata)),
                "entry_fill_candle": index,
                "entry_fill_time": candle.close_time.isoformat(),
                "entry_fill_price": entry,
                "entry_raw_fill_price": raw_entry,
                "entry_zone_low": signal.entry_zone_low or signal.entry_price,
                "entry_zone_high": signal.entry_zone_high or signal.entry_price,
                "entry_fill_model": "conservative_zone_boundary",
                "activation_wait_candles": (
                    0
                    if signal.activation_type is None
                    else max(
                        0,
                        index - int(metadata.get("activation_candle", index)),
                    )
                ),
            }
        assert entry is not None
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
                        stop_candle=candle,
                        config=config,
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
                        stop_candle=candle,
                        config=config,
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
    assert entry is not None
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
    zone_low = signal.entry_zone_low or signal.entry_price
    zone_high = signal.entry_zone_high or signal.entry_price
    return candle.high >= zone_low and candle.low <= zone_high


def _entry_zone_fill_price(signal: BacktestSignal, candle: Candle) -> float | None:
    """Return a conservative deterministic raw fill inside the touched entry zone."""

    zone_low = signal.entry_zone_low or signal.entry_price
    zone_high = signal.entry_zone_high or signal.entry_price
    overlap_low = max(candle.low, zone_low)
    overlap_high = min(candle.high, zone_high)
    if overlap_low > overlap_high:
        return None

    # Intrabar path is unknowable. Use the less favorable touched boundary:
    # longs fill at the highest overlapped price, shorts at the lowest.
    if signal.direction is TradeDirection.LONG:
        return overlap_high
    return overlap_low


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


def _diagnostic_recovery_entry_replay(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    entry_price: float,
    stop_price: float,
    target_price: float,
    config: BacktestConfig,
) -> dict[str, str | int | float | bool]:
    """Replay a fresh recovery entry without changing the stopped trade."""

    risk_per_unit = abs(entry_price - stop_price)
    if risk_per_unit <= 0.0 or not candles:
        return {
            "available": False,
            "outcome": "unavailable",
            "gross_r": 0.0,
            "net_r": 0.0,
            "bars_to_outcome": 0,
            "target_before_stop": False,
            "same_candle_ambiguous": False,
        }

    def stop_hit(candle: Candle) -> bool:
        return (
            candle.low <= stop_price
            if signal.direction is TradeDirection.LONG
            else candle.high >= stop_price
        )

    def target_hit(candle: Candle) -> bool:
        return (
            candle.high >= target_price
            if signal.direction is TradeDirection.LONG
            else candle.low <= target_price
        )

    def directional_r(exit_price: float) -> float:
        move = (
            exit_price - entry_price
            if signal.direction is TradeDirection.LONG
            else entry_price - exit_price
        )
        return move / risk_per_unit

    def cost_adjusted_r(exit_price: float) -> float:
        round_trip_cost = (
            (entry_price + exit_price) * (config.fee_pct + config.slippage_pct) / 100.0
        )
        return directional_r(exit_price) - round_trip_cost / risk_per_unit

    for index, candle in enumerate(candles, start=1):
        hit_stop = stop_hit(candle)
        hit_target = target_hit(candle)
        if hit_stop:
            return {
                "available": True,
                "outcome": "stop",
                "gross_r": directional_r(stop_price),
                "net_r": cost_adjusted_r(stop_price),
                "bars_to_outcome": index,
                "target_before_stop": False,
                "same_candle_ambiguous": hit_target,
            }
        if hit_target:
            return {
                "available": True,
                "outcome": "target",
                "gross_r": directional_r(target_price),
                "net_r": cost_adjusted_r(target_price),
                "bars_to_outcome": index,
                "target_before_stop": True,
                "same_candle_ambiguous": False,
            }

    final_close = candles[-1].close
    return {
        "available": True,
        "outcome": "expired",
        "gross_r": directional_r(final_close),
        "net_r": cost_adjusted_r(final_close),
        "bars_to_outcome": len(candles),
        "target_before_stop": False,
        "same_candle_ambiguous": False,
    }


def _recovery_identity_id(*parts: object) -> str:
    payload = "|".join(str(part) for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:20]


def _recovery_event_id(
    signal: BacktestSignal,
    *,
    reclaim_time: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
) -> str:
    """Return the current deterministic identity for one recovery event."""

    return _recovery_identity_id(
        signal.symbol,
        signal.direction.value,
        signal.strategy.value,
        reclaim_time,
        f"{entry_price:.12g}",
        f"{target_price:.12g}",
    )


def _strict_recovery_event_id(
    signal: BacktestSignal,
    *,
    reclaim_time: str,
    entry_price: float,
    stop_price: float,
    target_price: float,
) -> str:
    """Return a deliberately strict candidate-level recovery identity."""

    return _recovery_identity_id(
        signal.symbol,
        signal.direction.value,
        signal.strategy.value,
        signal.candidate_id or "",
        signal.generated_at.isoformat(),
        reclaim_time,
        f"{entry_price:.12g}",
        f"{stop_price:.12g}",
        f"{target_price:.12g}",
    )


def _loose_recovery_event_id(
    signal: BacktestSignal,
    *,
    reclaim_time: str,
) -> str:
    """Return a broad same-symbol/direction/reclaim identity for sensitivity."""

    return _recovery_identity_id(
        signal.symbol,
        signal.direction.value,
        reclaim_time,
    )


def _recovery_market_episode_id(
    signal: BacktestSignal,
    *,
    reclaim_time: str,
) -> str:
    """Group nearby cross-candidate recoveries into a broad market episode."""

    try:
        timestamp = datetime.fromisoformat(reclaim_time)
        bucket_minute = (
            timestamp.minute // RECOVERY_MARKET_EPISODE_MINUTES
        ) * RECOVERY_MARKET_EPISODE_MINUTES
        bucket = timestamp.replace(
            minute=bucket_minute,
            second=0,
            microsecond=0,
        ).isoformat()
    except ValueError:
        bucket = reclaim_time
    return _recovery_identity_id(
        signal.symbol,
        signal.direction.value,
        bucket,
    )


def _legacy_post_stop_thesis_metadata(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    entry: float,
    stop: float,
    stop_candle: Candle,
    config: BacktestConfig,
) -> dict[str, str | int | float | bool]:
    """Classify stop severity and a possible post-stop recovery setup.

    The original trade remains stopped. A later reclaim can only become a new,
    diagnostic recovery setup. The stop candle is included for breach depth and
    close acceptance, while later candles confirm reclaim, hold, retest, and
    target sequencing.
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
            "wick_only_stop_sweep": False,
            "sweep_reclaim_candidate": False,
            "sweep_reclaim_confirmed": False,
            "sweep_reclaim_rejected_reason": "invalid_risk_geometry",
            "reclaim_candle_body_ratio": 0.0,
            "reclaim_close_location": 0.0,
            "entry_level_reclaimed": False,
            "entry_level_held_next_candle": False,
            "retest_available": False,
            "retest_held": False,
            "remaining_target_room_r": 0.0,
            "recovery_entry_authorized": False,
            "recovery_entry_price": 0.0,
            "recovery_entry_candle": 0,
            "recovery_target_before_failure": False,
        }

    def beyond_stop_r(candle: Candle) -> float:
        if signal.direction is TradeDirection.LONG:
            return max(0.0, stop - candle.low) / risk_per_unit
        return max(0.0, candle.high - stop) / risk_per_unit

    def close_beyond_stop_r(candle: Candle) -> float:
        if signal.direction is TradeDirection.LONG:
            return max(0.0, stop - candle.close) / risk_per_unit
        return max(0.0, candle.close - stop) / risk_per_unit

    def traded_beyond_stop(candle: Candle) -> bool:
        return candle.low < stop if signal.direction is TradeDirection.LONG else candle.high > stop

    def closed_beyond_stop(candle: Candle) -> bool:
        return (
            candle.close < stop if signal.direction is TradeDirection.LONG else candle.close > stop
        )

    def stop_reclaimed_on_close(candle: Candle) -> bool:
        return (
            candle.close >= stop
            if signal.direction is TradeDirection.LONG
            else candle.close <= stop
        )

    def entry_reclaimed_on_close(candle: Candle) -> bool:
        return (
            candle.close >= entry
            if signal.direction is TradeDirection.LONG
            else candle.close <= entry
        )

    def entry_touched(candle: Candle) -> bool:
        return candle.low <= entry <= candle.high

    def favorable_close(candle: Candle, level: float) -> bool:
        return (
            candle.close >= level
            if signal.direction is TradeDirection.LONG
            else candle.close <= level
        )

    all_breach_candles = (stop_candle, *candles)
    maximum_beyond_stop_r = max(beyond_stop_r(candle) for candle in all_breach_candles)
    maximum_close_beyond_stop_r = max(close_beyond_stop_r(candle) for candle in all_breach_candles)
    bars_traded_beyond_stop = sum(traded_beyond_stop(candle) for candle in all_breach_candles)
    bars_closed_beyond_stop = sum(closed_beyond_stop(candle) for candle in all_breach_candles)

    consecutive_closes = 0
    maximum_consecutive_closes = 0
    for candle in all_breach_candles:
        if closed_beyond_stop(candle):
            consecutive_closes += 1
            maximum_consecutive_closes = max(
                maximum_consecutive_closes,
                consecutive_closes,
            )
        else:
            consecutive_closes = 0

    maximum_favorable_r = 0.0
    maximum_adverse_r = 0.0
    bars_to_stop_reclaim = 0
    bars_to_entry_reclaim = 0
    stop_reclaimed = stop_reclaimed_on_close(stop_candle)
    entry_reclaimed = entry_reclaimed_on_close(stop_candle)
    tp1_reached = False
    reclaim_candle: Candle | None = None
    reclaim_candle_index = 0

    for index, candle in enumerate(candles, start=1):
        favorable_r, adverse_r = _candle_excursions_r(signal, candle, entry)
        maximum_favorable_r = max(maximum_favorable_r, favorable_r)
        maximum_adverse_r = max(maximum_adverse_r, adverse_r)

        if not stop_reclaimed and stop_reclaimed_on_close(candle):
            stop_reclaimed = True
            bars_to_stop_reclaim = index
        if not entry_reclaimed and entry_reclaimed_on_close(candle):
            entry_reclaimed = True
            bars_to_entry_reclaim = index
        if reclaim_candle is None and entry_reclaimed_on_close(candle):
            reclaim_candle = candle
            reclaim_candle_index = index
        tp1_reached = tp1_reached or _target_hit(
            signal,
            candle,
            signal.target_price,
        )

    stop_candle_reclaimed = stop_reclaimed_on_close(stop_candle)
    wick_only_stop_sweep = (
        maximum_beyond_stop_r > STOP_BREACH_SHALLOW_MAX_R
        and close_beyond_stop_r(stop_candle) == 0.0
        and stop_candle_reclaimed
        and bars_closed_beyond_stop == 0
    )

    close_failure = (
        maximum_close_beyond_stop_r >= STOP_BREACH_DEEP_CLOSE_MIN_R
        or maximum_consecutive_closes >= STOP_BREACH_DEEP_CONSECUTIVE_CLOSES
    )
    slow_or_failed_reclaim = (
        not stop_reclaimed or bars_to_stop_reclaim > STOP_BREACH_DEEP_RECLAIM_BARS
    )
    deep_directional_failure = close_failure or (
        maximum_beyond_stop_r >= STOP_BREACH_DEEP_MIN_R
        and not wick_only_stop_sweep
        and slow_or_failed_reclaim
    )
    shallow_stop_sweep = (
        not deep_directional_failure
        and maximum_beyond_stop_r <= STOP_BREACH_SHALLOW_MAX_R
        and bars_closed_beyond_stop <= 1
        and stop_reclaimed
        and (
            stop_candle_reclaimed
            or 0 < bars_to_stop_reclaim <= STOP_BREACH_SHALLOW_RECLAIM_MAX_BARS
        )
    )
    sweep_reclaim_candidate = not deep_directional_failure and (
        shallow_stop_sweep or wick_only_stop_sweep
    )
    moderate_stop_breach = (
        not deep_directional_failure and not sweep_reclaim_candidate and maximum_beyond_stop_r > 0.0
    )

    reclaim_body_ratio = 0.0
    reclaim_close_location = 0.0
    remaining_target_room_r = 0.0
    recovery_entry_price = 0.0
    recovery_reclaim_time = ""
    recovery_event_id = ""
    entry_level_held_next_candle = False
    retest_available = False
    retest_held = False
    retest_entry_price = 0.0
    retest_entry_candle = 0
    recovery_target_before_failure = False

    if reclaim_candle is not None:
        candle_range = reclaim_candle.high - reclaim_candle.low
        if candle_range > 0.0:
            reclaim_body_ratio = abs(reclaim_candle.close - reclaim_candle.open) / candle_range
            if signal.direction is TradeDirection.LONG:
                reclaim_close_location = (reclaim_candle.close - reclaim_candle.low) / candle_range
            else:
                reclaim_close_location = (reclaim_candle.high - reclaim_candle.close) / candle_range

        recovery_entry_price = reclaim_candle.close
        recovery_reclaim_time = reclaim_candle.open_time.isoformat()
        recovery_event_id = _recovery_event_id(
            signal,
            reclaim_time=recovery_reclaim_time,
            entry_price=recovery_entry_price,
            stop_price=stop,
            target_price=signal.target_price,
        )
        remaining_target_room_r = (
            (signal.target_price - recovery_entry_price) / risk_per_unit
            if signal.direction is TradeDirection.LONG
            else (recovery_entry_price - signal.target_price) / risk_per_unit
        )

        next_index = reclaim_candle_index
        if next_index < len(candles):
            next_candle = candles[next_index]
            entry_level_held_next_candle = favorable_close(next_candle, entry)

        for later in candles[reclaim_candle_index:]:
            if closed_beyond_stop(later):
                break
            if entry_touched(later):
                retest_available = True
                if favorable_close(later, entry):
                    retest_held = True
                    if retest_entry_candle == 0:
                        retest_entry_price = later.close
                        retest_entry_candle = reclaim_candle_index + 1
            if _target_hit(signal, later, signal.target_price):
                recovery_target_before_failure = True
                break

    strong_reclaim_candle = (
        reclaim_candle is not None
        and reclaim_body_ratio >= SWEEP_RECLAIM_BODY_RATIO_MIN
        and reclaim_close_location >= SWEEP_RECLAIM_CLOSE_LOCATION_MIN
    )
    timely_reclaim = 0 < reclaim_candle_index <= SWEEP_RECLAIM_MAX_CONFIRM_BARS
    structure_confirmed = entry_level_held_next_candle or retest_held
    sweep_reclaim_confirmed = (
        sweep_reclaim_candidate
        and timely_reclaim
        and strong_reclaim_candle
        and remaining_target_room_r >= SWEEP_RECLAIM_MIN_REMAINING_TARGET_R
    )
    recovery_entry_authorized = (
        sweep_reclaim_confirmed and structure_confirmed and not deep_directional_failure
    )

    aggressive_replay: dict[str, str | int | float | bool] = {
        "available": False,
        "outcome": "unavailable",
        "gross_r": 0.0,
        "net_r": 0.0,
        "bars_to_outcome": 0,
        "target_before_stop": False,
        "same_candle_ambiguous": False,
    }
    retest_replay: dict[str, str | int | float | bool] = {
        "available": False,
        "outcome": "unavailable",
        "gross_r": 0.0,
        "net_r": 0.0,
        "bars_to_outcome": 0,
        "target_before_stop": False,
        "same_candle_ambiguous": False,
    }

    if sweep_reclaim_confirmed and reclaim_candle is not None:
        aggressive_replay = _diagnostic_recovery_entry_replay(
            signal,
            candles[reclaim_candle_index:],
            entry_price=recovery_entry_price,
            stop_price=stop,
            target_price=signal.target_price,
            config=config,
        )

    if sweep_reclaim_confirmed and retest_held and retest_entry_candle > 0:
        retest_replay = _diagnostic_recovery_entry_replay(
            signal,
            candles[retest_entry_candle:],
            entry_price=retest_entry_price,
            stop_price=stop,
            target_price=signal.target_price,
            config=config,
        )

    if deep_directional_failure:
        rejected_reason = "deep_directional_failure"
    elif not sweep_reclaim_candidate:
        rejected_reason = "not_a_sweep_candidate"
    elif reclaim_candle is None:
        rejected_reason = "entry_level_not_reclaimed"
    elif not timely_reclaim:
        rejected_reason = "reclaim_too_slow"
    elif not strong_reclaim_candle:
        rejected_reason = "weak_reclaim_candle"
    elif remaining_target_room_r < SWEEP_RECLAIM_MIN_REMAINING_TARGET_R:
        rejected_reason = "insufficient_remaining_target_room"
    elif not structure_confirmed:
        rejected_reason = "reclaim_not_held_or_retested"
    else:
        rejected_reason = "none"

    aggressive_available = bool(aggressive_replay.get("available"))
    retest_recovery_available = bool(retest_replay.get("available"))
    if aggressive_available and retest_recovery_available:
        recovery_entry_pair_classification = "both_available"
    elif aggressive_available:
        recovery_entry_pair_classification = "aggressive_only"
    elif retest_recovery_available:
        recovery_entry_pair_classification = "retest_only"
    else:
        recovery_entry_pair_classification = "neither_available"

    aggressive_net_r_value = float(aggressive_replay.get("net_r", 0.0))
    retest_net_r_value = float(retest_replay.get("net_r", 0.0))

    def projected_recovery_net_r(entry_price: float) -> tuple[float, float, float]:
        mode_risk = abs(entry_price - stop)
        if mode_risk <= 0.0:
            return 0.0, 0.0, 0.0
        target_move = (
            signal.target_price - entry_price
            if signal.direction is TradeDirection.LONG
            else entry_price - signal.target_price
        )
        gross_room_r = target_move / mode_risk
        round_trip_cost = (
            (entry_price + signal.target_price) * (config.fee_pct + config.slippage_pct) / 100.0
        )
        cost_drag_r = round_trip_cost / mode_risk
        return gross_room_r, cost_drag_r, gross_room_r - cost_drag_r

    aggressive_room_r = 0.0
    aggressive_cost_drag_r = 0.0
    aggressive_projected_net_r = 0.0
    if aggressive_available:
        (
            aggressive_room_r,
            aggressive_cost_drag_r,
            aggressive_projected_net_r,
        ) = projected_recovery_net_r(recovery_entry_price)

    retest_room_r = 0.0
    retest_cost_drag_r = 0.0
    retest_projected_net_r = 0.0
    if retest_recovery_available:
        (
            retest_room_r,
            retest_cost_drag_r,
            retest_projected_net_r,
        ) = projected_recovery_net_r(retest_entry_price)

    retest_delay_bars = (
        max(0, retest_entry_candle - reclaim_candle_index) if retest_recovery_available else 0
    )

    raw_timeframe = getattr(signal, "timeframe", "unknown")
    recovery_timeframe = str(getattr(raw_timeframe, "value", raw_timeframe))
    timeframe_expected_bars = {
        "1m": 4.0,
        "3m": 5.0,
        "5m": 6.0,
        "15m": 8.0,
        "30m": 10.0,
        "1h": 12.0,
        "4h": 16.0,
    }.get(recovery_timeframe, 8.0)

    pre_entry_ranges = [
        max(0.0, candle.high - candle.low)
        for candle in candles[: max(1, reclaim_candle_index)]
        if candle.high > candle.low
    ]
    recent_ranges = pre_entry_ranges[-8:]
    recent_average_range = sum(recent_ranges) / len(recent_ranges) if recent_ranges else 0.0

    def attainability_diagnostics(
        *,
        available: bool,
        entry_price: float,
        projected_net_r: float,
        structure_held: bool,
    ) -> tuple[float, float, float, float, str]:
        if not available or entry_price <= 0.0:
            return 0.0, 0.0, 0.0, 0.0, "invalid"

        target_move = abs(signal.target_price - entry_price)
        target_range_multiple = (
            target_move / recent_average_range if recent_average_range > 0.0 else 0.0
        )
        expected_bars = target_range_multiple

        body_quality = min(
            1.0,
            reclaim_body_ratio / max(SWEEP_RECLAIM_BODY_RATIO_MIN, 1e-9),
        )
        close_quality = min(
            1.0,
            reclaim_close_location / max(SWEEP_RECLAIM_CLOSE_LOCATION_MIN, 1e-9),
        )
        structure_quality = 1.0 if structure_held else 0.0
        reclaim_quality = (
            0.45 + 0.25 * body_quality + 0.20 * close_quality + 0.10 * structure_quality
        )

        stretch_factor = (
            min(1.0, timeframe_expected_bars / expected_bars) if expected_bars > 0.0 else 1.0
        )
        attainability_factor = max(0.20, min(1.0, reclaim_quality * stretch_factor))
        attainable_projected_net_r = projected_net_r * attainability_factor

        if attainable_projected_net_r >= 0.30:
            viability = "viable"
        elif attainable_projected_net_r > 0.0:
            viability = "marginal"
        else:
            viability = "weak"

        return (
            target_range_multiple,
            expected_bars,
            attainability_factor,
            attainable_projected_net_r,
            viability,
        )

    (
        aggressive_target_range_multiple,
        aggressive_expected_bars,
        aggressive_attainability_factor,
        aggressive_attainable_projected_net_r,
        aggressive_attainability_viability,
    ) = attainability_diagnostics(
        available=aggressive_available,
        entry_price=recovery_entry_price,
        projected_net_r=aggressive_projected_net_r,
        structure_held=entry_level_held_next_candle,
    )
    (
        retest_target_range_multiple,
        retest_expected_bars,
        retest_attainability_factor,
        retest_attainable_projected_net_r,
        retest_attainability_viability,
    ) = attainability_diagnostics(
        available=retest_recovery_available,
        entry_price=retest_entry_price,
        projected_net_r=retest_projected_net_r,
        structure_held=retest_held,
    )

    aggressive_preference_score = aggressive_projected_net_r + (
        0.10 if entry_level_held_next_candle else 0.0
    )
    retest_preference_score = (
        retest_projected_net_r
        + (0.10 if retest_held else 0.0)
        - min(0.25, 0.05 * retest_delay_bars)
    )

    def recovery_mode_viability(
        *,
        available: bool,
        projected_net_r: float,
    ) -> str:
        if not available:
            return "invalid"
        if projected_net_r >= 0.30:
            return "viable"
        if projected_net_r > 0.0:
            return "marginal"
        return "weak"

    aggressive_viability = recovery_mode_viability(
        available=aggressive_available,
        projected_net_r=aggressive_projected_net_r,
    )
    retest_viability = recovery_mode_viability(
        available=retest_recovery_available,
        projected_net_r=retest_projected_net_r,
    )

    if aggressive_available and retest_recovery_available:
        aggressive_gate = aggressive_viability == "viable"
        retest_gate = retest_viability == "viable"
        both_below_absolute_gate = not aggressive_gate and not retest_gate

        if both_below_absolute_gate:
            recovery_selector_outcome = "abstain_both_weak"
            recovery_selector_reason = "neither mode clears absolute projected net R gate"
        elif aggressive_gate and not retest_gate:
            recovery_selector_outcome = "select_aggressive"
            recovery_selector_reason = "only aggressive mode clears absolute viability"
        elif retest_gate and not aggressive_gate:
            recovery_selector_outcome = "select_retest"
            recovery_selector_reason = "only retest mode clears absolute viability"
        elif aggressive_preference_score >= retest_preference_score + 0.10:
            recovery_selector_outcome = "select_aggressive"
            recovery_selector_reason = "aggressive preference score leads by minimum margin"
        elif retest_preference_score >= aggressive_preference_score + 0.10:
            recovery_selector_outcome = "select_retest"
            recovery_selector_reason = "retest preference score leads by minimum margin"
        else:
            recovery_selector_outcome = "no_clear_preference"
            recovery_selector_reason = "viable modes are too close to separate"
    elif aggressive_available:
        recovery_selector_outcome = "single_mode_aggressive"
        recovery_selector_reason = "only aggressive mode is available"
    elif retest_recovery_available:
        recovery_selector_outcome = "single_mode_retest"
        recovery_selector_reason = "only retest mode is available"
    else:
        recovery_selector_outcome = "reject_no_viable_mode"
        recovery_selector_reason = "no recovery entry mode is available"

    recovery_pair_predicted_mode = {
        "select_aggressive": "prefer_aggressive",
        "select_retest": "prefer_retest",
        "no_clear_preference": "no_clear_preference",
        "abstain_both_weak": "no_clear_preference",
        "single_mode_aggressive": "single_mode_aggressive",
        "single_mode_retest": "single_mode_retest",
        "reject_no_viable_mode": "no_mode_available",
    }[recovery_selector_outcome]

    if aggressive_available and retest_recovery_available:
        recovery_pair_net_r_delta = aggressive_net_r_value - retest_net_r_value
        if recovery_pair_net_r_delta > 0.0:
            recovery_pair_realized_winner = "aggressive"
        elif recovery_pair_net_r_delta < 0.0:
            recovery_pair_realized_winner = "retest"
        else:
            recovery_pair_realized_winner = "tie"
    else:
        recovery_pair_net_r_delta = 0.0
        recovery_pair_realized_winner = "not_comparable"

    aggressive_profitable = aggressive_net_r_value >= 0.30
    retest_profitable = retest_net_r_value >= 0.30
    if aggressive_available and retest_recovery_available:
        if aggressive_profitable and retest_profitable:
            recovery_selector_realized_classification = "both_profitable"
        elif aggressive_profitable:
            recovery_selector_realized_classification = "aggressive_profitable"
        elif retest_profitable:
            recovery_selector_realized_classification = "retest_profitable"
        elif aggressive_net_r_value <= 0.0 and retest_net_r_value <= 0.0:
            recovery_selector_realized_classification = "both_negative"
        else:
            recovery_selector_realized_classification = "both_below_gate"
    else:
        recovery_selector_realized_classification = "not_comparable"

    recovery_selector_evaluable = aggressive_available and retest_recovery_available
    if recovery_selector_outcome == "select_aggressive":
        recovery_selector_correct = (
            aggressive_profitable and aggressive_net_r_value >= retest_net_r_value
        )
    elif recovery_selector_outcome == "select_retest":
        recovery_selector_correct = (
            retest_profitable and retest_net_r_value >= aggressive_net_r_value
        )
    elif recovery_selector_outcome == "abstain_both_weak":
        recovery_selector_correct = recovery_selector_realized_classification in {
            "both_negative",
            "both_below_gate",
        }
    elif recovery_selector_outcome == "no_clear_preference":
        recovery_selector_correct = recovery_pair_realized_winner == "tie"
    else:
        recovery_selector_correct = False

    recovery_pair_directional_prediction_evaluable = recovery_pair_predicted_mode in {
        "prefer_aggressive",
        "prefer_retest",
    }
    recovery_pair_abstention = recovery_selector_outcome in {
        "no_clear_preference",
        "abstain_both_weak",
    }
    recovery_pair_abstention_correct = recovery_pair_abstention and recovery_selector_correct

    if recovery_pair_directional_prediction_evaluable:
        recovery_pair_prediction_correct = (
            recovery_pair_predicted_mode == "prefer_aggressive"
            and recovery_pair_realized_winner == "aggressive"
        ) or (
            recovery_pair_predicted_mode == "prefer_retest"
            and recovery_pair_realized_winner == "retest"
        )
        recovery_pair_evaluation = "correct" if recovery_pair_prediction_correct else "incorrect"
    elif recovery_pair_abstention:
        recovery_pair_prediction_correct = recovery_pair_abstention_correct
        recovery_pair_evaluation = (
            "abstention_correct" if recovery_pair_abstention_correct else "abstention_missed"
        )
    else:
        recovery_pair_prediction_correct = False
        recovery_pair_evaluation = "not_evaluable"

    recovery_event_id_strict = ""
    recovery_event_id_loose = ""
    recovery_market_episode_id = ""
    if recovery_reclaim_time:
        recovery_event_id_strict = _strict_recovery_event_id(
            signal,
            reclaim_time=recovery_reclaim_time,
            entry_price=recovery_entry_price,
            stop_price=stop,
            target_price=signal.target_price,
        )
        recovery_event_id_loose = _loose_recovery_event_id(
            signal,
            reclaim_time=recovery_reclaim_time,
        )
        recovery_market_episode_id = _recovery_market_episode_id(
            signal,
            reclaim_time=recovery_reclaim_time,
        )

    later_recovery_after_directional_failure = deep_directional_failure and (
        entry_reclaimed or tp1_reached
    )

    if not candles:
        classification = "ambiguous_after_stop"
    elif deep_directional_failure:
        classification = (
            "deep_directional_failure_then_recovery"
            if later_recovery_after_directional_failure
            else "deep_directional_failure"
        )
    elif recovery_entry_authorized:
        classification = "qualified_sweep_reclaim_setup"
    elif sweep_reclaim_confirmed:
        classification = "sweep_reclaim_confirmed_waiting_hold"
    elif wick_only_stop_sweep:
        classification = "wick_only_sweep_unqualified"
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
        "post_stop_max_consecutive_closes_beyond_stop": (maximum_consecutive_closes),
        "post_stop_entry_reclaimed": entry_reclaimed,
        "post_stop_stop_reclaimed": stop_reclaimed,
        "post_stop_bars_to_reclaim": bars_to_entry_reclaim,
        "post_stop_bars_to_stop_reclaim": bars_to_stop_reclaim,
        "post_stop_first_recovery_candle": reclaim_candle_index,
        "post_stop_tp1_reached": tp1_reached,
        "post_stop_maximum_favorable_excursion_r": maximum_favorable_r,
        "post_stop_maximum_adverse_excursion_r": maximum_adverse_r,
        "post_stop_adverse_close_beyond_stop": bars_closed_beyond_stop > 0,
        "shallow_stop_sweep": shallow_stop_sweep,
        "moderate_stop_breach": moderate_stop_breach,
        "deep_directional_failure": deep_directional_failure,
        "directional_failure_before_recovery": deep_directional_failure,
        "later_recovery_after_directional_failure": (later_recovery_after_directional_failure),
        "wick_only_stop_sweep": wick_only_stop_sweep,
        "sweep_reclaim_candidate": sweep_reclaim_candidate,
        "sweep_reclaim_confirmed": sweep_reclaim_confirmed,
        "sweep_reclaim_rejected_reason": rejected_reason,
        "reclaim_candle_body_ratio": reclaim_body_ratio,
        "reclaim_close_location": reclaim_close_location,
        "entry_level_reclaimed": reclaim_candle is not None,
        "entry_level_held_next_candle": entry_level_held_next_candle,
        "retest_available": retest_available,
        "retest_held": retest_held,
        "remaining_target_room_r": remaining_target_room_r,
        "recovery_entry_authorized": recovery_entry_authorized,
        "recovery_entry_price": recovery_entry_price,
        "recovery_entry_candle": reclaim_candle_index,
        "recovery_reclaim_time": recovery_reclaim_time,
        "recovery_event_id": recovery_event_id,
        "recovery_event_id_strict": recovery_event_id_strict,
        "recovery_event_id_loose": recovery_event_id_loose,
        "recovery_market_episode_id": recovery_market_episode_id,
        "recovery_entry_pair_classification": recovery_entry_pair_classification,
        "recovery_pair_available": (aggressive_available and retest_recovery_available),
        "recovery_pair_predicted_mode": recovery_pair_predicted_mode,
        "recovery_pair_realized_winner": recovery_pair_realized_winner,
        "recovery_pair_net_r_delta": recovery_pair_net_r_delta,
        "recovery_pair_prediction_correct": recovery_pair_prediction_correct,
        "recovery_pair_evaluation": recovery_pair_evaluation,
        "recovery_pair_directional_prediction_evaluable": (
            recovery_pair_directional_prediction_evaluable
        ),
        "recovery_pair_abstention": recovery_pair_abstention,
        "recovery_pair_abstention_correct": recovery_pair_abstention_correct,
        "recovery_pair_aggressive_remaining_room_r": aggressive_room_r,
        "recovery_pair_retest_remaining_room_r": retest_room_r,
        "recovery_pair_aggressive_cost_drag_r": aggressive_cost_drag_r,
        "recovery_pair_retest_cost_drag_r": retest_cost_drag_r,
        "recovery_pair_aggressive_projected_net_r": aggressive_projected_net_r,
        "recovery_pair_retest_projected_net_r": retest_projected_net_r,
        "recovery_pair_aggressive_preference_score": aggressive_preference_score,
        "recovery_pair_retest_preference_score": retest_preference_score,
        "recovery_pair_retest_delay_bars": retest_delay_bars,
        "recovery_attainability_timeframe": recovery_timeframe,
        "recovery_attainability_expected_bars_profile": timeframe_expected_bars,
        "recovery_attainability_recent_average_range": recent_average_range,
        "recovery_pair_aggressive_target_range_multiple": aggressive_target_range_multiple,
        "recovery_pair_retest_target_range_multiple": retest_target_range_multiple,
        "recovery_pair_aggressive_expected_bars": aggressive_expected_bars,
        "recovery_pair_retest_expected_bars": retest_expected_bars,
        "recovery_pair_aggressive_attainability_factor": aggressive_attainability_factor,
        "recovery_pair_retest_attainability_factor": retest_attainability_factor,
        "recovery_pair_aggressive_attainable_projected_net_r": (
            aggressive_attainable_projected_net_r
        ),
        "recovery_pair_retest_attainable_projected_net_r": (retest_attainable_projected_net_r),
        "recovery_pair_aggressive_attainability_viability": (aggressive_attainability_viability),
        "recovery_pair_retest_attainability_viability": (retest_attainability_viability),
        "recovery_attainability_diagnostic_only": True,
        "recovery_attainability_production_behavior_changed": False,
        "recovery_selector_outcome": recovery_selector_outcome,
        "recovery_selector_reason": recovery_selector_reason,
        "recovery_selector_aggressive_viability": aggressive_viability,
        "recovery_selector_retest_viability": retest_viability,
        "recovery_selector_realized_classification": (recovery_selector_realized_classification),
        "recovery_selector_evaluable": recovery_selector_evaluable,
        "recovery_selector_correct": recovery_selector_correct,
        "recovery_target_before_failure": recovery_target_before_failure,
        "aggressive_reclaim_entry_available": bool(aggressive_replay.get("available")),
        "aggressive_reclaim_entry_price": recovery_entry_price,
        "aggressive_reclaim_stop_price": stop,
        "aggressive_reclaim_target_price": signal.target_price,
        "aggressive_reclaim_outcome": str(aggressive_replay.get("outcome", "unavailable")),
        "aggressive_reclaim_gross_r": float(aggressive_replay.get("gross_r", 0.0)),
        "aggressive_reclaim_net_r": aggressive_net_r_value,
        "aggressive_reclaim_target_reached": aggressive_replay.get("outcome") == "target",
        "aggressive_reclaim_positive_net": aggressive_net_r_value > 0.0,
        "aggressive_reclaim_net_r_gate_passed": (
            aggressive_net_r_value >= RECOVERY_MINIMUM_NET_R_GATE
        ),
        "aggressive_reclaim_bars_to_outcome": int(aggressive_replay.get("bars_to_outcome", 0)),
        "aggressive_reclaim_target_before_stop": bool(aggressive_replay.get("target_before_stop")),
        "aggressive_reclaim_same_candle_ambiguous": bool(
            aggressive_replay.get("same_candle_ambiguous")
        ),
        "retest_recovery_entry_available": bool(retest_replay.get("available")),
        "retest_recovery_entry_price": retest_entry_price,
        "retest_recovery_stop_price": stop,
        "retest_recovery_target_price": signal.target_price,
        "retest_recovery_outcome": str(retest_replay.get("outcome", "unavailable")),
        "retest_recovery_gross_r": float(retest_replay.get("gross_r", 0.0)),
        "retest_recovery_net_r": retest_net_r_value,
        "retest_recovery_target_reached": retest_replay.get("outcome") == "target",
        "retest_recovery_positive_net": retest_net_r_value > 0.0,
        "retest_recovery_net_r_gate_passed": (retest_net_r_value >= RECOVERY_MINIMUM_NET_R_GATE),
        "retest_recovery_bars_to_outcome": int(retest_replay.get("bars_to_outcome", 0)),
        "retest_recovery_target_before_stop": bool(retest_replay.get("target_before_stop")),
        "retest_recovery_same_candle_ambiguous": bool(retest_replay.get("same_candle_ambiguous")),
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


_SWEEP_RECLAIM_PARITY_KEYS = (
    "post_stop_maximum_excursion_beyond_stop_r",
    "post_stop_maximum_close_beyond_stop_r",
    "post_stop_bars_closed_beyond_stop",
    "post_stop_max_consecutive_closes_beyond_stop",
    "post_stop_stop_reclaimed",
    "post_stop_bars_to_stop_reclaim",
    "post_stop_entry_reclaimed",
    "post_stop_bars_to_reclaim",
    "shallow_stop_sweep",
    "wick_only_stop_sweep",
    "deep_directional_failure",
    "sweep_reclaim_candidate",
    "sweep_reclaim_confirmed",
    "sweep_reclaim_rejected_reason",
    "reclaim_candle_body_ratio",
    "reclaim_close_location",
    "entry_level_reclaimed",
    "retest_held",
    "remaining_target_room_r",
    "recovery_entry_authorized",
    "recovery_entry_price",
    "recovery_entry_candle",
)


def _post_stop_thesis_metadata(
    signal: BacktestSignal,
    candles: Sequence[Candle],
    *,
    entry: float,
    stop: float,
    stop_candle: Candle,
    config: BacktestConfig,
) -> dict[str, str | int | float | bool]:
    """Preserve legacy authority while recording shared-evaluator parity."""

    legacy = _legacy_post_stop_thesis_metadata(
        signal,
        candles,
        entry=entry,
        stop=stop,
        stop_candle=stop_candle,
        config=config,
    )
    shared = sweep_reclaim_metadata(
        assess_post_stop_sweep_reclaim(
            signal,
            entry_price=entry,
            stop_price=stop,
            stop_candle=stop_candle,
            confirmation_candles=candles,
        )
    )
    mismatches = tuple(
        key
        for key in _SWEEP_RECLAIM_PARITY_KEYS
        if not _sweep_reclaim_values_match(legacy.get(key), shared.get(key))
    )
    return {
        **legacy,
        "shared_sweep_reclaim_state": shared["shared_sweep_reclaim_state"],
        "shared_sweep_reclaim_parity": not mismatches,
        "shared_sweep_reclaim_mismatch_count": len(mismatches),
        "shared_sweep_reclaim_mismatch_fields": ",".join(mismatches),
    }


def _sweep_reclaim_values_match(left: object, right: object) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left is right
    if isinstance(left, int | float) and isinstance(right, int | float):
        return abs(float(left) - float(right)) <= 1e-9
    return left == right
