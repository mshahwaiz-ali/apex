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
    candles: Sequence