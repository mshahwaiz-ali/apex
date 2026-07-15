"""Application boundary for repeatable P1 paper-operation cycles."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Protocol

from apex.data.providers.errors import MarketDataProviderError
from apex.domain.models import Candle
from apex.paper_trading.contracts import PaperTradeConfig
from apex.paper_trading.operations import Paper