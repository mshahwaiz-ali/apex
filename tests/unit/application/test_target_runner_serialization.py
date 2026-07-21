from __future__ import annotations

import json
from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.target_runner_serialization import (
    serialize_assessment_target_runner_diagnostics,
    serialize_setup_target_runner_diagnostics,
)


def test_serialization_exposes_complete_target_and_runner_fields() -> None:
    assessment = build_discovery_assessment(_selection())

    payload = serialize_assessment_target_runner_diagnostics(assessment)

    assert payload["symbol"] == "TESTUSDT"
    selected = payload["selected_setup"]
    assert isinstance(selected, dict)
    assert {
        "candidate_id",
        "runner_qualified",
        "runner_qualification_reason",
        "targets",
        "management_policies",
    } == set(selected)

    targets = selected["targets"]
    assert isinstance(targets, list)
    assert targets
    assert {
        "label",
        "price",
        "reward",
        "risk_reward",
        "partial_close_pct",
        "target_type",
        "purpose",
        "target_basis",
        "target_timeframe",
        "target_role",
        "synthetic",
        "runner_qualified",
        "rationale",
    } == set(targets[0])


def test_serialization_is_json_safe_and_deterministic() -> None:
    assessment = build_discovery_assessment(_selection())

    first = serialize_assessment_target_runner_diagnostics(assessment)
    second = serialize_assessment_target_runner_diagnostics(assessment)

    assert first == second
    assert json.loads(json.dumps(first)) == first


def test_one_tp1_without_runner_remains_valid_and_serializable() -> None:
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    setup = assessment.setup
    one_target = replace(
        setup,
        take_profits=(
            replace(
                setup.take_profits[0],
                label="TP1",
                partial_close_pct=100.0,
                runner_qualified=False,
            ),
        ),
        runner_qualified=False,
        runner_qualification_reason="no qualified extension target",
    )

    payload = serialize_setup_target_runner_diagnostics(one_target)

    assert payload["runner_qualified"] is False
    assert payload["runner_qualification_reason"] == ("no qualified extension target")
    assert len(payload["targets"]) == 1
    assert payload["targets"][0]["label"] == "TP1"
    assert payload["targets"][0]["partial_close_pct"] == 100.0


def test_serializer_does_not_change_setup_authority() -> None:
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    setup = assessment.setup
    before = (
        setup.candidate_id,
        setup.execution_allowed_now,
        setup.runner_qualified,
        tuple(target.label for target in setup.take_profits),
        tuple(target.partial_close_pct for target in setup.take_profits),
    )

    serialize_setup_target_runner_diagnostics(setup)

    after = (
        setup.candidate_id,
        setup.execution_allowed_now,
        setup.runner_qualified,
        tuple(target.label for target in setup.take_profits),
        tuple(target.partial_close_pct for target in setup.take_profits),
    )
    assert before == after


def test_selected_and_developing_setups_share_identical_schema() -> None:
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    mirrored = replace(
        assessment,
        developing_setup=replace(
            assessment.setup,
            candidate_id="developing-shadow",
            execution_allowed_now=False,
        ),
    )

    payload = serialize_assessment_target_runner_diagnostics(mirrored)

    selected = payload["selected_setup"]
    developing = payload["developing_setup"]
    assert isinstance(selected, dict)
    assert isinstance(developing, dict)
    assert set(selected) == set(developing)
    assert set(selected["targets"][0]) == set(developing["targets"][0])
    assert set(selected["management_policies"][0]) == set(developing["management_policies"][0])
