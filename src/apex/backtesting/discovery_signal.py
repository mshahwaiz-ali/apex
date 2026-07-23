"""Build normalized backtest signals from discovery setups."""

from __future__ import annotations

from apex.application.discovery_contracts import DiscoverySetup
from apex.backtesting.contracts import BacktestActivationType, BacktestSignal
from apex.data.timeframes import timeframe_delta


def signal_from_discovery_setup(
    setup: DiscoverySetup,
    *,
    replay_timeframe: str | None = None,
    replay_source: str = "production",
) -> BacktestSignal:
    """Convert one discovery setup into a one-unit structural replay signal.

    Quantity is normalized to one market unit. Risk amount is the structural
    entry-to-stop distance for that unit, so realized R is measured from the
    trade geometry itself.
    """

    targets = setup.take_profits
    conditional = setup.conditional_plan
    expiry_candles = setup.setup_expiry_bars
    if (
        expiry_candles is None
        and setup.setup_expiry_seconds is not None
        and replay_timeframe is not None
    ):
        interval_seconds = int(timeframe_delta(replay_timeframe).total_seconds())
        expiry_candles = max(
            1,
            (setup.setup_expiry_seconds + interval_seconds - 1) // interval_seconds,
        )
    return BacktestSignal(
        symbol=setup.symbol,
        strategy=setup.strategy,
        direction=setup.direction,
        generated_at=setup.decision_time,
        entry_price=setup.entry.preferred,
        entry_zone_low=setup.entry.lower,
        entry_zone_high=setup.entry.upper,
        stop_price=setup.stop_loss.price,
        target_price=targets[0].price,
        quantity=1.0,
        risk_amount=abs(setup.entry.preferred - setup.stop_loss.price),
        confidence_score=setup.confidence_score,
        target_prices=tuple(target.price for target in targets),
        partial_close_percentages=tuple(target.partial_close_pct for target in targets),
        activation_type=(
            None if conditional is None else BacktestActivationType(conditional.trigger.kind.value)
        ),
        activation_level=(None if conditional is None else conditional.trigger.level),
        pre_entry_invalidation_price=(
            None if conditional is None else conditional.pre_entry_invalidation.price
        ),
        maximum_chase_price=(None if conditional is None else setup.entry.maximum_chase_price),
        activation_expiry_candles=(None if conditional is None else expiry_candles),
        candidate_id=setup.candidate_id,
        replay_source=replay_source,
        strategy_version=setup.strategy_version,
        setup_methodology_version=setup.methodology_version,
        setup_validity=setup.setup_validity.value,
        execution_authority=setup.execution_authority.value,
    )


__all__ = ["signal_from_discovery_setup"]
