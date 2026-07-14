"""Chronological full-pipeline backtest orchestration."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from apex.application.analysis import SymbolAnalysis, analyze_symbol, serialize_symbol_analysis
from apex.application.chronological_metadata import (
    ChronologicalBacktestMetadata,
    build_chronological_metadata,
)
from