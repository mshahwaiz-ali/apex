from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apex.domain.futures import EntryState
from apex.strategies.context import TimeframeRole
from apex.strategies.contracts import StrategyType
from apex.strategies.diagnostics import Phase4RejectionCode, build_phase4_diagnostics
from apex.structure.contracts import TrendDirection
from apex.structure.regime import MarketRegime


def _context(
    *,
    trend: TrendDirection,
    momentum: tuple[float, float, float],