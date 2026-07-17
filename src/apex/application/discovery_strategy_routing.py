"""Stage 3 strategy enablement and transparent routing diagnostics."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.strategies import (
    CandidateActionability,
    EntryStatus,
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
    """Apply only explicit strategy enablement; default to every evaluated family."""

    enabled = _enabled_strategies(
        strategy_analysis.evaluated_strategies,
        routing_config,
    )
    candidates = tuple(
        candidate
        for candidate in strategy_analysis.candidates
        if candidate.strategy in enabled
    )
    actionability_by_candidate = {
        entry.candidate