"""Focused tests for the backtest sweep/reclaim adapter."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from apex.backtesting.contracts import BacktestSignal
from apex.backtesting.sweep_reclaim_adapter import (
    assess_post_stop_sweep_reclaim,
    sweep_reclaim_metadata,
)
from apex.domain.models import Candle
from apex.domain.sweep_reclaim import SweepReclaimState
from apex.strategies import StrategyType, TradeDirection


_BASE_TIME = datetime(2026, 7, 24, 12, 0, tzinfo=