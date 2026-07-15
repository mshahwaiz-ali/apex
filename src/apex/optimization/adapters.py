"""Adapters from Apex historical result payloads into optimization summaries."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from apex.optimization.contracts import PerformanceSummary
from apex.optimization.engine import performance_from_mapping


def performance_from_spot_historical_payload(payload: Mapping[str, Any]) -> PerformanceSummary:
    """Build optimization input from a persisted S