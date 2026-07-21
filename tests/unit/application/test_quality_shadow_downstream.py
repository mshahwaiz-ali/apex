from __future__ import annotations

import ast
import json
from pathlib import Path

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment


def test_discovery_assessment_attaches_post_selection_shadow_diagnostics() -> None:
    selection = _selection()
    selected_before = selection.selected_candidate
    order_before = tuple(item.scored.candidate_id for item in selection.ranked_candidates)
    outcomes_before = tuple(item.outcome for item in selection.ranked_candidates)

    assessment = build_discovery_assessment(selection)

    assert assessment.quality_shadow_diagnostics is not None
    diagnostics = assessment.quality_shadow_diagnostics
    assert diagnostics["shadow_only"] is True
    assert diagnostics["selected_candidate_id"] == "alpha"
    assert diagnostics["candidate_order"] == ["alpha", "beta"]
    assert json.loads(json.dumps(diagnostics)) == diagnostics
    assert selection.selected_candidate is selected_before
    assert tuple(item.scored.candidate_id for item in selection.ranked_candidates) == order_before
    assert tuple(item.outcome for item in selection.ranked_candidates) == outcomes_before


def test_downstream_attachment_preserves_selected_setup() -> None:
    selection = _selection()
    assessment = build_discovery_assessment(selection)
    assert assessment.setup is not None
    assert assessment.setup.candidate_id == "alpha"
    assert assessment.setup.confidence_score == selection.selected_candidate.final_score
    assert assessment.reasons == ()


def test_downstream_attachment_preserves_rejection_authority() -> None:
    selection = _selection()
    selected_before = selection.selected_candidate
    rejected_before = selection.rejected_candidates
    no_trade_before = selection.no_trade_reason
    build_discovery_assessment(selection)
    assert selection.selected_candidate is selected_before
    assert selection.rejected_candidates == rejected_before
    assert selection.no_trade_reason == no_trade_before


def test_shared_discovery_path_attaches_diagnostics_after_selection() -> None:
    source = Path("src/apex/application/discovery_setup.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    function = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "build_discovery_assessment"
    )
    calls = [
        node
        for node in ast.walk(function)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "build_quality_shadow_rollout_diagnostics"
    ]
    assert len(calls) == 1


def test_shadow_diagnostics_are_additive_to_discovery_contract() -> None:
    source = Path("src/apex/application/discovery_contracts.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assessment = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "DiscoveryAssessment"
    )
    fields = {
        node.target.id
        for node in assessment.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    assert "quality_shadow_diagnostics" in fields
