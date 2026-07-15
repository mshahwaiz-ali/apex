from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from apex.application.analysis import (
    build_strategy_context,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
)
from apex.domain import Candle, GainerStateThresholds
from apex.domain.models import (
    ExchangeFilterSnapshot,
    LiquidationCluster,
    LiquidationClusterSide,
    LiquidationClusterSnapshot,
    OrderBookLevel,
    OrderBookSnapshot,
    TickerSnapshot,
)
from apex.strategies import TimeframeRole
