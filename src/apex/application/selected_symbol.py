"""Application service for user-selected futures market analysis."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime

from apex.application.decision_analysis import SymbolAnalysis, analyze_symbol
from apex.application.symbols import normalize_market_symbol
from apex.data.providers.base import MarketDataProvider


def analyze_selected_symbol(
    symbol: str,
    provider: