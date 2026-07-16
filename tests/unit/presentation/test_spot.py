"""Tests for trader-facing spot workflow presentation."""

from __future__ import annotations

from apex.presentation.spot import render_spot_analysis, render_spot_plan, render_spot_scan


def _planning_payload() -> dict[str, object]:
    return {
        "entry_plan": {"primary_entry_price": 100.0, "maximum_entry_price": 102.0},
        "stop_plan": {"stop_price": 94.0, "risk_percentage": 6.0},
        "position_plan": {"quote_allocation": 250.0, "quantity": 2.5},
        "target_plan": {"primary_target_price": 115.0, "risk_reward": 2.5},
        "lifecycle": {"state": "planned", "time_exit_candles": 24},
    }


def test_spot_analysis_renders_selected_strategy_and_plan() -> None:
    payload = {
        "schema_version": 1,
        "selected_strategy": {
            "strategy": "higher_timeframe_trend_pullback",
            "decision": "APPROVE",
            "eligibility": "PAPER_ONLY",
            "thesis": "Higher-timeframe trend remains intact near support.",
            "invalidation_price": 94.0,
            "evidence": ["support held", "relative strength positive"],
            "rejection_reasons": [],
            "warnings": [],
        },
        "candidates": [],
        "planning": _planning_payload(),
        "warnings": ["research guidance only"],
    }

    rendered = render_spot_analysis(payload)

    assert "Spot Analysis" in rendered
    assert "Selected Strategy" in rendered
    assert "Higher Timeframe Trend Pullback" in rendered
    assert "Entry Plan" in rendered
    assert "Risk and Allocation" in rendered
    assert '"selected_strategy"' not in rendered


def test_spot_analysis_explains_no_approved_setup() -> None:
    payload = {
        "schema_version": 1,
        "selected_strategy": None,
        "candidates": [
            {
                "strategy": "breakout_retest",
                "decision": "REJECT",
                "rejection_reasons": ["retest did not hold"],
            }
        ],
        "planning": None,
        "warnings": [],
    }

    rendered = render_spot_analysis(payload)

    assert "No approved spot setup" in rendered
    assert "Why No Setup" in rendered
    assert "retest did not hold" in rendered


def test_spot_analysis_verbose_adds_candidate_review_and_warnings() -> None:
    payload = {
        "selected_strategy": None,
        "candidates": [
            {
                "strategy": "accumulation_range_breakout",
                "decision": "WATCH",
                "rejection_reasons": [],
            }
        ],
        "planning": None,
        "warnings": ["paper validation required"],
    }

    text = render_spot_analysis(payload)
    verbose = render_spot_analysis(payload, mode="verbose")

    assert "Candidate Review" not in text
    assert "Candidate Review" in verbose
    assert "Research Warnings" in verbose


def test_spot_plan_renders_bounded_position_sections() -> None:
    payload = {**_planning_payload(), "warnings": ["research guidance only"]}

    rendered = render_spot_plan(payload)

    assert "Spot Position Plan" in rendered
    assert "Entry Plan" in rendered
    assert "Targets" in rendered
    assert "Lifecycle" in rendered


def test_spot_scan_renders_ranked_and_failure_summaries() -> None:
    payload = {
        "schema_version": 2,
        "mode": "eligible",
        "ranked": [
            {
                "rank": 1,
                "symbol": "BTCUSDT",
                "analysis": {
                    "selected_strategy": {"strategy": "breakout_retest"},
                    "planning": _planning_payload(),
                },
            }
        ],
        "ineligible": [
            {
                "symbol": "ETHUSDT",
                "eligibility_status": "reviewable",
                "reason_codes": ["terminal_extension"],
            }
        ],
        "failures": [{"symbol": "SOLUSDT", "error": "provider unavailable"}],
        "warnings": [],
    }

    text = render_spot_scan(payload)
    verbose = render_spot_scan(payload, mode="verbose")

    assert "Spot Market Scan" in text
    assert "#1 BTCUSDT" in text
    assert "plan available" in text
    assert "Failures" in text
    assert "Ineligible" not in text
    assert "Ineligible" in verbose
