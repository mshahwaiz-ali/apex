"""Application service for user-selected market analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from apex.application.analysis import SymbolAnalysis, analyze_symbol
from apex.application.symbols import normalize_market_symbol
from apex.config.settings import DEFAULT_TIMEFRAME_MAX_STALENESS_SECONDS
from apex.data.providers.base import MarketDataProvider
from apex.risk import DEFAULT_RISK_CONFIG, ExposureState, RiskConfig
