from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import cast

from tests.unit.strategies.test_candidate_execution_quality import _candidate

from apex.application.opportunity_portfolio import OpportunityLane
from apex.scoring.candidate_quality_components import (
    attach_candidate_quality_components,
    candidate_quality_shadow_payload,
)
from apex.strategies.context import StrategyContext


def _context() -> StrategyContext:
    return cast(
        StrategyContext,
        SimpleNamespace(decision_frame=SimpleNamespace(data_confidence=0.88, is_stale=False)),
    )


def _attached():
    candidate = _candidate()
    candidate = replace(
        candidate,
        score_dimensions=replace(
            candidate.score_dimensions, execution_quality=64.0, rank_score=77.0
        ),
    )
    return attach_candidate_quality_components(
        candidate=candidate, context=_context(), lane=OpportunityLane.CMP_SCALP
    )


def test_shadow_payload_is_structured_json_safe_and_explicit() -> None:
    payload = candidate_quality_shadow_payload(_attached())
    assert payload is not None
    assert payload["version"] == 1
    assert payload["shadow_only"] is True
    assert payload["lane"] == "cmp_scalp"
    assert payload["confidence_semantics"] == "evidence_strength"
    assert payload["calibrated_probability"] is False
    assert json.loads(json.dumps(payload)) == payload


def test_shadow_payload_preserves_rank_score() -> None:
    candidate = _attached()
    rank_before = candidate.score_dimensions.rank_score
    payload = candidate_quality_shadow_payload(candidate)
    assert payload is not None
    assert candidate.score_dimensions.rank_score == rank_before


def test_unattached_candidate_does_not_fabricate_payload() -> None:
    assert candidate_quality_shadow_payload(_candidate()) is None


def test_payload_exposes_independent_components_and_sources() -> None:
    payload = candidate_quality_shadow_payload(_attached())
    assert payload is not None
    decomposed = payload["decomposed_values"]
    assert isinstance(decomposed, dict)
    assert set(decomposed) == {
        "pattern_confidence",
        "directional_alignment",
        "setup_quality",
        "execution_quality",
        "reward_quality",
        "timing_quality",
        "data_confidence",
        "overall_trade_quality",
    }
    sources = payload["component_sources"]
    assert isinstance(sources, dict)
    assert "overall_trade_quality" in sources
