"""Market-environment-aware wrappers for live analysis and scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from apex.application import analysis as _analysis
from apex.data.providers.base import MarketDataProvider
from apex.domain import GainerStateThresholds, MarketCategory, ScannerMode
from apex.domain.models import Candle
from