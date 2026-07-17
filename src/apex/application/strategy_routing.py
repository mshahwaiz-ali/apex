"""Deterministic strategy-routing metadata for scanner and analysis output."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.config import DEFAULT_STRATEGY_ROUTING
from apex.strategies import (
    StrategyAnalysisResult,
    StrategyType,
    SuppressedStrategyCandidate,
    TradeCandidate,
    strategy_evidence_payload,
    strategy_evidence_summary,
)


def apply_strategy_routing(
    strategy_analysis: StrategyAnalysisResult,
    *,
    routing_config: Mapping[str, Sequence[str]] | None = None,
) -> StrategyAnalysisResult:
    """Filter candidates