from __future__ import annotations

from collections.abc import Iterable

from apex.presentation.operator_output import render_analysis, render_scan


def _setup() -> dict[str, object]:
    return {
        "direction": "long",
        "strategy": "breakout_continuation",
        "entry_status": "READY_NOW",
        "actionability_state": "EXECUTE_NOW",
        "actionability_basis": "cmp_inside_entry_zone",
        "confidence_score": 84.0,
        "execution_allowed_now": True,
        "entry": {
            "current_price": 100.0,
            "lower": 99.5,
            "upper": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 101.0,
            "distance_from_current": 0.0,
        },
        "stop_loss": {
            "price": 97.0,
            "single_buffer_rationale": "Below accepted structure",
        },
        "take_profits": (
            {"price": 103.0, "risk_reward": 1.0, "purpose": "Reduce risk"},
            {"price": 106.0, "risk_reward": 2.0, "purpose": "Primary objective"},
            {"price": 109.0, "risk_reward": 3.0, "purpose": "Runner objective"},
        ),
        "quality_dimensions": {
            "setup_quality": 84.0,
            "execution_quality": 79.0,
            "continuation_quality": 76.0,
            "overall_trade_quality": 81.0,
        },
        "initial_risk_reward": 1.0,
        "runner_risk_reward": 3.0,
        "alignment_classification": "aligned",
        "evidence": ("Breakout accepted", "Volume expanded"),
        "warnings": ("Failure below accepted structure",),
        "entry_rationale": "CMP is inside the executable zone",
        "target_rationale": "Targets follow visible resistance",
        "maximum_chase_rationale": "Beyond this price reward-to-risk degrades",
    }


def _assert_snapshot_contract(output: str, expected: Iterable[str]) -> None:
    missing = tuple(label for label in expected if label not in output)
    assert missing == (), f"missing snapshot fields: {missing}\n\n{output}"


def test_compact_scan_snapshot_preserves_essential_trading_information() -> None:
    setup = _setup()
    output = render_scan(
        {
            "total_analysis_count": 3,
            "displayed_analysis_count": 1,
            "selected_setup_count": 1,
            "long_candidate_count": 1,
            "short_candidate_count": 0,
            "results": (
                {
                    "symbol": "BTCUSDT",
                    "setup": setup,
                    "methodology_completeness": {
                        "unavailable_fields": ("depth_imbalance",),
                    },
                },
            ),
        }
    )

    _assert_snapshot_contract(
        output,
        (
            "Enter at CMP",
            "BTCUSDT",
            "Action",
            "Execute now",
            "Side",
            "Strategy",
            "CMP",
            "Entry",
            "Preferred",
            "Stop",
            "TP1",
            "TP2",
            "TP3",
            "Trade quality",
            "Execution quality",
            "Data warning",
            "Main risk",
        ),
    )


def test_detailed_analysis_snapshot_preserves_geometry_and_diagnostics() -> None:
    setup = _setup()
    output = render_analysis(
        {
            "symbol": "BTCUSDT",
            "setup": setup,
            "nearby_alternative": {
                **setup,
                "actionability_state": "PLACE_LIMIT",
                "entry_status": "WAIT_FOR_RETEST",
            },
            "opposite_follow_up": {
                **setup,
                "direction": "short",
                "strategy": "range_reversal",
                "actionability_state": "WAIT_FOR_RECLAIM",
                "entry_status": "WAIT_FOR_RECLAIM",
            },
            "developing_setup": {
                **setup,
                "strategy": "trend_pullback",
                "actionability_state": "APPROACHING_ENTRY",
                "entry_status": "APPROACHING_ENTRY",
            },
            "reasons": ("Breakout accepted",),
            "multi_timeframe_map": {
                "5m": {"structure": "bullish", "momentum": "expanding"},
                "1h": {"structure": "bullish", "momentum": "stable"},
            },
            "opportunity_collision": {"resolution": "coexist"},
            "runner_decision": {"decision": "tighten_and_hold"},
            "rejected_candidates": (
                {
                    "direction": "short",
                    "strategy": "failed_breakout",
                    "reason": "No downside acceptance",
                },
            ),
            "methodology_completeness": {
                "unavailable_fields": ("liquidation_impulse",),
            },
        },
        explain=True,
    )

    _assert_snapshot_contract(
        output,
        (
            "APEX ANALYSIS",
            "Decision",
            "ENTER LONG",
            "Actionability",
            "Execute now",
            "Trade plan",
            "Current price",
            "Entry zone",
            "Preferred entry",
            "Do not chase above",
            "Stop",
            "TP1",
            "TP2",
            "TP3",
            "Why this trade",
            "Opportunity map",
            "Current opportunity",
            "Nearby alternative",
            "Opposite follow-up",
            "Developing setup",
            "Multi-timeframe view",
            "Geometry rationale",
            "Evidence and contradictions",
            "Lifecycle and collision",
            "Collision",
            "Runner",
            "Rejected candidates",
            "Data quality",
        ),
    )
