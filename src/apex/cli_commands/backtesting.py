"""Focused public chronological backtest command."""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Annotated

import typer

from apex.application import analyze_selected_symbol, bootstrap, create_market_data_services
from apex.backtesting.contracts import BacktestConfig
from apex.backtesting.discovery_signal import signal_from_discovery_setup
from apex.backtesting.engine import simulate_trade, summarize_trades
from apex.backtesting.historical_signal_replay import (
    HistoricalCandleSeries,
    HistoricalCandleStore,
    HistoricalReplayProvider,