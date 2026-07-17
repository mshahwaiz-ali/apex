"""Market-environment-aware wrappers for live analysis and scanning."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application import analysis as _analysis
from apex.application.market_strategy_router import route_market_strategies
from