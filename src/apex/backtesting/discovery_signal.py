"""Build normalized backtest signals from discovery setups."""

from __future__ import annotations

from apex.application.discovery_contracts import DiscoverySetup
from apex.backtesting.contracts import BacktestSignal


def signal_from_discovery_setup(setup: DiscoverySetup) -> BacktestSignal:
    """Convert one discovery setup into a one-unit structural replay signal.

    Quantity is normalized to one market unit. Risk amount is the structural
    entry-to-stop distance for that unit, so realized R remains independent of
    wallet balance, leverage, margin, or position sizing.
    """

    targets = setup.take_profits
    return BacktestSignal(
        symbol=setup.symbol,
        strategy=setup.strategy,
        direction=setup.direction,
        generated_at=setup.decision_time,
        entry_price=setup.entry.preferred,
        stop_price=setup.stop_loss.price,
        target_price=targets[0].price,
        quantity=1.0,
        risk_amount=abs(setup.entry.preferred - setup.stop_loss.price),
        confidence_score=setup.confidence_score,
        target_prices=tuple(target.price for target in targets),
        partial_close_percentages=tuple(target.partial_close_pct for target in targets),
    )


__all__ = ["signal_from_discovery_setup"]
