from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pytest
from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.opportunity_portfolio import OpportunityLane
from apex.scoring.candidate_quality_components import (
    attach_candidate_quality_components,
    build_candidate_quality_shadow_diagnostics,
    derive_candidate_quality_components,
)
from apex.strategies.context import StrategyContext
from apex.strategies.contracts import TradeCandidate


def _context() -> StrategyContext:
    return cast(
        StrategyContext,
        SimpleNamespace(
            decision_frame=SimpleNamespace(
                data_confidence=0.91,
                is_stale=False,
            )
        ),
    )


def _prepared_candidate() -> TradeCandidate:
    candidate = _candidate()
    return replace(
        candidate,
        score_dimensions=replace(
            candidate.score_dimensions,
            execution_quality=63.0,
            rank_score=82.0,
        ),
    )


def test_shadow_comparison_records_legacy_decomposed_and_delta_values() -> None:
    candidate = _prepared_candidate()
    derived = derive_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.CMP_SCALP,
    )

    diagnostics = build_candidate_quality_shadow_diagnostics(
        candidate=candidate,
        derived=derived,
    )

    assert diagnostics.lane is OpportunityLane.CMP_SCALP
    assert diagnostics.confidence_semantics == "evidence_strength"
    assert diagnostics.calibrated_probability is False
    assert diagnostics.legacy_values["trend_alignment"] == pytest.approx(
        candidate.quality.trend_alignment * 100.0
    )
    assert diagnostics.decomposed_values["overall_trade_quality"] == pytest.approx(
        derived.overall.overall_trade_quality
    )


def test_shadow_attachment_exposes_diagnostics_without_changing_authority() -> None:
    candidate = _prepared_candidate()

    attached = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.NEARBY_STRUCTURED,
    )

    assert attached.symbol == candidate.symbol
    assert attached.strategy == candidate.strategy
    assert attached.direction == candidate.direction
    assert attached.decision_time == candidate.decision_time
    assert attached.entry == candidate.entry
    assert attached.entry_opportunities == candidate.entry_opportunities
    assert attached.invalidation == candidate.invalidation
    assert attached.targets == candidate.targets
    assert attached.quality == candidate.quality
    assert attached.evidence == candidate.evidence
    assert attached.lifecycle == candidate.lifecycle
    assert attached.provisional == candidate.provisional
    assert attached.layered_state == candidate.layered_state
    assert attached.score_dimensions.rank_score == candidate.score_dimensions.rank_score

    assert attached.metadata["quality_decomposition_shadow_only"] is True
    assert attached.metadata["quality_shadow_diagnostics_version"] == 1
    assert "trend_alignment=" in str(attached.metadata["quality_shadow_legacy_values"])
    assert "overall_trade_quality=" in str(attached.metadata["quality_shadow_decomposed_values"])
    assert "execution_quality_minus_entry_quality=" in str(
        attached.metadata["quality_shadow_deltas"]
    )


def test_shadow_metadata_is_deterministic() -> None:
    candidate = _prepared_candidate()

    first = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.RUNNER,
    )
    second = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.RUNNER,
    )

    assert first.metadata == second.metadata
    assert first.score_dimensions == second.score_dimensions


def test_strategy_orchestration_does_not_consume_shadow_quality_for_authority() -> None:
    source = Path("src/apex/strategies/orchestration.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    forbidden = {
        "overall_trade_quality",
        "quality_shadow_deltas",
        "quality_shadow_legacy_values",
        "quality_shadow_decomposed_values",
        "rank_score",
    }
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attrs = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert forbidden.isdisjoint(names)
    assert forbidden.isdisjoint(attrs)


def test_shadow_attachment_preserves_candidate_ordering_key_inputs() -> None:
    first = _prepared_candidate()
    second = replace(
        _prepared_candidate(),
        metadata={**_prepared_candidate().metadata, "candidate_id": "second"},
    )
    original = (first, second)
    attached = tuple(
        attach_candidate_quality_components(
            candidate=candidate,
            context=_context(),
            lane=OpportunityLane.DEVELOPING,
        )
        for candidate in original
    )

    original_order = tuple(
        (candidate.strategy, candidate.decision_time, candidate.metadata.get("candidate_id"))
        for candidate in original
    )
    attached_order = tuple(
        (candidate.strategy, candidate.decision_time, candidate.metadata.get("candidate_id"))
        for candidate in attached
    )
    assert attached_order == original_order
