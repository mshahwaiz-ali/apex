"""Phase 4 strategy-candidate orchestration."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType

from apex.strategies.context import StrategyContext
from apex.strategies.contracts import StrategyType, TradeCandidate
from apex.strategies.diagnostics import (
    StrategyDiagnostic,
    build_phase4_diagnostics,
    has_higher_timeframe_breakout,