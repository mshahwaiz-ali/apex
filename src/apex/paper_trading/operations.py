"""Deterministic provider-independent P1 paper operations."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from apex.domain.models import Candle
from apex.paper_trading.contracts import PaperTrade, PaperTradeConfig
from apex.paper_trading.forward_validation import (
    ForwardPaperDailyReport,
    build_forward_paper_daily_report,
    write_forward_paper_daily_report,
)
from apex.paper_trading.management import advance_paper_trade
from apex.paper_trading.store import PaperTradeStore


@dataclass(frozen=True, slots=True)
class PaperOperationCycleResult:
    """Immutable outcome of one spot or futures paper-operation cycle."""

    market_type: str
    started_at: datetime
    completed