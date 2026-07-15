"""Operational status inspection for sustained P1 paper validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, cast

from apex.paper_trading.store import PaperTradeStore

_SUPPORTED_MARKETS = ("futures", "spot")


@dataclass(frozen=True, slots=True)
class MarketOperationsStatus:
    """Scheduler and