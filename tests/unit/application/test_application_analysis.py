from datetime import UTC, datetime, timedelta

import pytest

from apex.application.analysis import (
    build_strategy_context,
    load_symbols,
    scan_symbols,
    serialize_scan_result,
)
from apex.domain import Candle
from apex.domain.models import TickerSnapshot
from apex.strategies import TimeframeRole

NOW = datetime(2026, 7, 13, tzinfo