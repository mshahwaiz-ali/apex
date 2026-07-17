"""Discovery-neutral analysis orchestration for live scan and analyze flows."""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from apex.application.candidate_ranking import (
    build_candidate_ranking_snapshot,
    candidate_ranking_payload,
)
from apex.application.discovery_context import (
    build_strategy_context,
    frame_data_quality_payload,
)
from apex.application.discovery_contracts import ScanResult, SymbolAnalysis
from apex.application.discovery_setup import build_discovery_assessment
from apex.application.futures_quality import analyze_futures_phase5
from apex.application.market_strategy_router import MarketStrategyRoute
from apex.application.precision_entry import build_precision_entry_plan
from apex.application.strategy_routing import (
    apply_strategy_routing,
    build_strategy_routing_payload,
)
from apex.data.providers.base import MarketDataProvider
from apex.strategies import (
    analyze_strategies,
