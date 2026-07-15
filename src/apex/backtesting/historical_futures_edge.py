"""Build setup-specific historical edge reports from completed futures campaigns."""

from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.backtesting.contracts import BacktestOutcome, BacktestSignal, SimulatedTrade
from apex.backtesting.historical_edge import (
    DEFAULT_EDGE_SEGMENTS,
    HistoricalEdgeProfile,
    aggregate_historical_edges,
)
from apex.backtesting.historical_edge_io import build_historical_edge_report
from apex.strategies import StrategyType, TradeDirection

H