"""Canonical strategy-routing analysis orchestration."""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from apex.application import integrated_analysis as _integrated
from apex.application.discovery_contracts import ScanResult
from apex.application.market_strategy_router import (
    MarketStrategyRoute,
    market_strategy_route_payload,
    route_market_strategies,
)
from apex.data.providers.base import MarketDataProvider
from apex.market_environment import DEFAULT_MARKET_ENVIRONMENT_CONFIG, MarketEnvironmentConfig

DEFAULT_SCAN_DISPLAY_LIMIT = 15


@dataclass(frozen=True, slots=True)
class SymbolAnalysis(_integrated.SymbolAnalysis):
    """Integrated discovery analysis enriched with market strategy routing."""

    market_strategy_route: MarketStrategyRoute | None = None


load_symbols = _integrated.load_symbols
write_json_report = _integrated.write_json_report


def analyze_symbol(
    symbol: str,
    provider: MarketDataProvider,
    *,
    timeframes: Sequence[str],
    timeframe_roles