"""Tests for non-authoritative old-versus-new rollout diagnostics."""

from __future__ import annotations

from apex.application.rollout_comparison import (
    analysis_comparison_payload,
    compare_analysis_outputs,
)


def _legacy_payload() -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "setup": {
            "strategy": "breakout_retest",
            "direction": "long",
            "entry_status": "ready_now",
            "confidence_score": 72.0,
            "entry": {
                "lower": 100.0,
                "upper": 101.0,
                "preferred": 100.5,
                "maximum_chase": 101.5,
            },
            "stop_loss": {"price": 98.0},
            "take_profits": [
                {"label": "TP1", "price": 104.0, "risk_reward": 1.4},
                {"label": "TP2", "price": 107.0, "risk_reward": 2.6},
            ],
        },
        "entry_state": "execute_now",
        "confidence_score": 72.0,
        "quality_score": 72.0,
        "reasons": [],
    }


def _new_payload() -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "opportunity_portfolio": {
            "primary_opportunity_id": "candidate-1",
            "opportunity_count": 1,
            "public_decision": "actionable_at_cmp",
            "current_long": {
                "opportunity_id": "candidate-1",
                "strategy": "breakout_retest",
                "direction": "long",
                "entry_status": "ready_now",
                "entry_zone": {
                    "lower": 100.0,
                    "upper": 101.0,
                    "preferred": 100.5,
                    "maximum_chase": 101.5,
                },
                "stop": 98.0,
                "targets": [
                    {"label": "TP1", "price": 104.0, "risk_reward": 1.4},
                    {"label": "TP2", "price": 107.0, "risk_reward": 2.6},
                ],
                "actionability_state": {"state": "execute_now"},
                "confidence_score": 72.0,
                "quality_score": 72.0,
            },
            "current_short": None,
            "nearby_long": None,
            "nearby_short": None,
            "follow_up_opportunities": [],
            "runner_plan": None,
        },
        "rejection_reasons": [],
    }


def test_equal_projections_report_no_differences() -> None:
    report = compare_analysis_outputs(_legacy_payload(), _new_payload())

    assert report.matches is True
    assert report.symbol == "BTCUSDT"
    assert report.legacy_opportunity_count == 1
    assert report.new_opportunity_count == 1
    assert report.differences == ()


def test_reports_multi_opportunity_and_geometry_differences() -> None:
    new_payload = _new_payload()
    portfolio = new_payload["opportunity_portfolio"]
    assert isinstance(portfolio, dict)
    portfolio["opportunity_count"] = 2
    portfolio["nearby_short"] = {
        "opportunity_id": "candidate-2",
        "strategy": "liquidity_sweep",
        "direction": "short",
        "entry_status": "watch_near_entry",
        "entry_zone": {
            "lower": 108.0,
            "upper": 109.0,
            "preferred": 108.5,
            "maximum_chase": 107.5,
        },
        "stop": 111.0,
        "targets": [{"label": "TP1", "price": 104.0, "risk_reward": 1.5}],
        "actionability_state": {"state": "place_limit_with_activation"},
    }
    current_long = portfolio["current_long"]
    assert isinstance(current_long, dict)
    current_long["stop"] = 97.5
    current_long["actionability_state"] = {"state": "execute_on_micro_confirmation"}

    report = compare_analysis_outputs(_legacy_payload(), new_payload)

    assert report.matches is False
    differences = {item.field: item for item in report.differences}
    assert differences["opportunity_count"].legacy == 1
    assert differences["opportunity_count"].new == 2
    assert differences["stop"].legacy == 98.0
    assert differences["stop"].new == 97.5
    assert differences["actionability_state"].legacy == "execute_now"
    assert differences["actionability_state"].new == "execute_on_micro_confirmation"


def test_missing_values_are_reported_without_fabrication() -> None:
    report = compare_analysis_outputs(
        {"symbol": "ETHUSDT", "setup": None, "reasons": ["legacy rejected"]},
        {
            "symbol": "ETHUSDT",
            "opportunity_portfolio": {
                "opportunity_count": 0,
                "public_decision": "no_valid_setup",
            },
            "rejection_reasons": ["new rejected"],
        },
    )

    differences = {item.field: item for item in report.differences}
    assert "selected_strategy" not in differences
    assert differences["actionability_state"].legacy is None
    assert differences["actionability_state"].new == "no_valid_setup"
    assert differences["rejection_reasons"].legacy == ("legacy rejected",)
    assert differences["rejection_reasons"].new == ("new rejected",)


def test_serialized_report_is_explicitly_non_authoritative() -> None:
    payload = analysis_comparison_payload(
        compare_analysis_outputs(_legacy_payload(), _new_payload())
    )

    assert payload["matches"] is True
    assert payload["authoritative"] is False
    assert "does not change selection" in str(payload["interpretation"])
