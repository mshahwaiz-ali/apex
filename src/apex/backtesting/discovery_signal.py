"""Build normalized backtest signals from discovery setups."""

from __future__ import annotations

from apex.application.discovery_contracts import DiscoverySetup
from apex.backtesting.contracts import BacktestSignal


def signal_from_discovery_setup(setup: DiscoverySetup) -> BacktestSignal:
    """Convert one discovery setup into a one-unit structural replay signal.

    Quantity is normalized to one market unit. ``