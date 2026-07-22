from __future__ import annotations

from apex.presentation.operator_output import (
    _opportunity_execution_fields,
    _opportunity_htf_fields,
)


def test_conditional_setup_is_labeled_as_future_not_no_trade() -> None:
    setup = {
        "entry_status": "WATCH_NEAR_ENTRY",
        "execution_allowed_now": False,
        "conditional_plan": {
            "trigger": {
                "condition": "close through the preferred trigger level",
            }
        },
    }
    fields = dict(_opportunity_execution_fields(setup))
    assert fields["Setup availability"] == "Future setup - activation required"
    assert fields["Execution authorized now"] == "No"
    assert fields["Execution reason"] == "close through the preferred trigger level"


def test_executable_setup_is_labeled_explicitly() -> None:
    setup = {
        "entry_status": "READY_NOW",
        "execution_allowed_now": True,
    }
    fields = dict(_opportunity_execution_fields(setup))
    assert fields["Setup availability"] == "Executable now"
    assert fields["Execution authorized now"] == "Yes"


def test_missed_setup_is_not_presented_as_future_setup() -> None:
    setup = {
        "actionability_state": "MISSED_OR_CHASING",
        "execution_allowed_now": False,
    }
    fields = dict(_opportunity_execution_fields(setup))
    assert fields["Setup availability"] == "Missed or chasing"
    assert fields["Execution authorized now"] == "No"


def test_htf_treatment_and_severity_are_rendered_when_available() -> None:
    setup = {
        "htf_consequence": {
            "execution_treatment": "conditional_confirmation",
            "severity": "strong",
            "score_penalty_points": 18.0,
        }
    }
    fields = dict(_opportunity_htf_fields(setup))
    assert fields["HTF treatment"] == "Conditional confirmation"
    assert fields["HTF severity"] == "Strong"
    assert fields["HTF score penalty"] == "18 points"


def test_missing_htf_payload_adds_no_fake_claims() -> None:
    assert _opportunity_htf_fields({}) == ()
