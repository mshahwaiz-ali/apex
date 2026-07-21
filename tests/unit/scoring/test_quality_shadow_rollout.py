from __future__ import annotations

import json
from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import cast

from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.opportunity_portfolio import OpportunityLane
from apex.scoring.candidate_quality_components import (
    attach_candidate_quality_components,
)
from apex.scoring.contracts import (
    CandidateOutcome,
    CandidateSelectionResult,
    ConflictSummary,
    DirectionalConsensus,
    RankedCandidate,
    ScoreBreakdown,
    ScoredCandidate,
)
from apex.scoring.quality_shadow_rollout import (
    build_quality_shadow_rollout_diagnostics,
)
from apex.strategies.context import StrategyContext
from apex.strategies.strategy_types import StrategyType


def _context() -> StrategyContext:
    return cast(
        StrategyContext,
        SimpleNamespace(
            decision_frame=SimpleNamespace(
                data_confidence=0.9,
                is_stale=False,
            )
        ),
    )


def _ranked(candidate_id: str, rank: int, score: float) -> RankedCandidate:
    candidate = _candidate()
    candidate = replace(
        candidate,
        metadata={**candidate.metadata, "candidate_id": candidate_id},
        score_dimensions=replace(
            candidate.score_dimensions,
            execution_quality=70.0 - rank,
            rank_score=score,
        ),
    )
    candidate = attach_candidate_quality_components(
        candidate=candidate,
        context=_context(),
        lane=OpportunityLane.CMP_SCALP,
    )
    scored = ScoredCandidate(
        candidate_id=candidate_id,
        candidate=candidate,
        breakdown=ScoreBreakdown(
            quality_points={"legacy_quality": score},
            penalty_points={},
            base_score=score,
            total_penalty=0.0,
            final_score=score,
        ),
        normalized_metrics={"legacy_quality": score / 100.0},
    )
    return RankedCandidate(
        scored=scored,
        rank=rank,
        outcome=CandidateOutcome.ACCEPTED,
        reasons=(),
        tie_break=(candidate_id,),
    )


def _selection() -> CandidateSelectionResult:
    ranked = (
        _ranked("alpha", 1, 82.0),
        _ranked("beta", 2, 74.0),
    )
    return CandidateSelectionResult(
        symbol="TESTUSDT",
        decision_time=datetime(2026, 7, 21, tzinfo=UTC),
        all_scored_candidates=tuple(item.scored for item in ranked),
        ranked_candidates=ranked,
        rejected_candidates=(),
        conflict_summary=ConflictSummary(
            directional_consensus=DirectionalConsensus.LONG,
            long_count=2,
            short_count=0,
            duplicate_groups=(),
            warnings=(),
        ),
        directional_consensus=DirectionalConsensus.LONG,
        selected_candidate=ranked[0],
        no_trade_reason=None,
        evaluated_strategy_order=(StrategyType.MOMENTUM_SCALP,),
        configuration_id="test-config",
        metadata={"authority": "legacy_selection"},
    )


def test_rollout_preserves_authoritative_order_and_selection() -> None:
    selection = _selection()
    before_order = tuple(item.scored.candidate_id for item in selection.ranked_candidates)
    before_selected = selection.selected_candidate

    diagnostics = build_quality_shadow_rollout_diagnostics(selection)

    assert diagnostics.candidate_order == before_order
    assert diagnostics.selected_candidate_id == "alpha"
    assert selection.selected_candidate is before_selected
    assert tuple(item.scored.candidate_id for item in selection.ranked_candidates) == before_order


def test_rollout_preserves_outcomes_scores_and_rejection_authority() -> None:
    selection = _selection()
    before = tuple(
        (
            item.scored.candidate_id,
            item.rank,
            item.outcome,
            item.final_score,
            item.reasons,
        )
        for item in selection.ranked_candidates
    )

    diagnostics = build_quality_shadow_rollout_diagnostics(selection)

    after = tuple(
        (
            item.scored.candidate_id,
            item.rank,
            item.outcome,
            item.final_score,
            item.reasons,
        )
        for item in selection.ranked_candidates
    )
    assert diagnostics.shadow_only is True
    assert before == after


def test_rollout_records_lane_components_sources_and_overall_score() -> None:
    diagnostics = build_quality_shadow_rollout_diagnostics(_selection())

    first = diagnostics.records[0]
    payload = first.payload

    assert first.candidate_id == "alpha"
    assert first.rank == 1
    assert first.selected is True
    assert payload["lane"] == "cmp_scalp"
    assert payload["confidence_semantics"] == "evidence_strength"
    assert payload["calibrated_probability"] is False
    assert "decomposed_values" in payload
    assert "component_sources" in payload
    assert "deltas" in payload


def test_rollout_is_deterministic_and_json_safe() -> None:
    selection = _selection()

    first = build_quality_shadow_rollout_diagnostics(selection).to_dict()
    second = build_quality_shadow_rollout_diagnostics(selection).to_dict()

    assert first == second
    assert json.loads(json.dumps(first)) == first


def test_unattached_candidates_are_omitted_not_fabricated() -> None:
    selection = _selection()
    plain = _candidate()
    plain_scored = replace(
        selection.ranked_candidates[0].scored,
        candidate=plain,
        candidate_id="plain",
    )
    plain_ranked = replace(
        selection.ranked_candidates[0],
        scored=plain_scored,
        tie_break=("plain",),
    )
    modified = replace(
        selection,
        all_scored_candidates=(plain_scored,),
        ranked_candidates=(plain_ranked,),
        selected_candidate=plain_ranked,
    )

    diagnostics = build_quality_shadow_rollout_diagnostics(modified)

    assert diagnostics.records == ()
    assert diagnostics.candidate_order == ()
    assert diagnostics.selected_candidate_id is None
