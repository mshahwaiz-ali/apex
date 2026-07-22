from __future__ import annotations

from apex.presentation.operator_output import render_analysis, render_scan


def _opportunity(identifier: str) -> dict[str, object]:
    setup = {
        "direction": "long",
        "strategy": "breakout_retest",
        "entry_status": "READY_NOW",
        "actionability_state": "EXECUTE_NOW",
        "entry": {
            "current_price": 100.0,
            "lower": 99.5,
            "upper": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 101.0,
            "rationale": "CMP remains inside accepted structure",
        },
        "stop_loss": {
            "price": 97.0,
            "rationale": "below structural invalidation",
        },
        "take_profits": [{"price": 106.0, "risk_reward": 2.0}],
        "target_rationale": "visible resistance provides target room",
        "maximum_chase_rationale": "reward-to-risk degrades above chase boundary",
        "evidence": ["volume expansion", "accepted retest"],
        "warnings": ["higher-timeframe resistance remains"],
    }
    return {
        **setup,
        "opportunity_id": identifier,
        "category": "current",
        "sequence_role": "current",
        "methodology_verdict": {"status": "allowed"},
        "setup": setup,
    }


def _payload() -> dict[str, object]:
    opportunity = _opportunity("btc-current")
    return {
        "symbol": "BTCUSDT",
        "methodology_gate_mode": "enforce",
        "methodology_completeness": {
            "unavailable_fields": ["liquidation_impulse"],
        },
        "multi_timeframe_map": {
            "5m": {"structure": "bullish", "momentum": "expanding"},
            "1h": {"structure": "bullish", "summary": "above reclaimed support"},
        },
        "opportunity_collision": {"resolution": "coexist"},
        "rejected_candidates": [
            {
                "direction": "short",
                "strategy": "failed_breakout",
                "reason": f"rejection {index}",
            }
            for index in range(10)
        ],
        "outcome_tracking": {
            "enabled": True,
            "database": "data/reports/analysis.db",
        },
        "historical_calibration": {
            "available": False,
            "reason": "insufficient resolved outcomes",
        },
        "opportunity_portfolio": {
            "cmp": 100.0,
            "decision": "current_opportunity",
            "analysis_mode": "selected_symbol",
            "opportunity_count": 1,
            "current_opportunities": [opportunity],
            "nearby_opportunities": [],
            "follow_up_opportunities": [],
            "runner_opportunities": [],
            "opportunities": [opportunity],
        },
        "setup_plan": {
            "status": "current_opportunity",
            "geometry_available": True,
            "opportunity_count": 1,
            "primary_opportunity_id": "btc-current",
        },
    }


def test_analysis_explain_appends_complete_diagnostics_after_setup_plan() -> None:
    rendered = render_analysis(_payload(), explain=True)

    assert rendered.index("Setup plan") < rendered.index("Methodology enforcement")
    for heading in (
        "Methodology enforcement",
        "Opportunity portfolio",
        "Multi-timeframe evidence",
        "Entry, stop, target, and chase rationale",
        "Supporting evidence",
        "Contradictions",
        "Missing evidence",
        "Collision and sequence",
        "Rejected and suppressed candidates",
        "Data quality",
        "Outcome-tracking status",
        "Historical calibration",
    ):
        assert heading in rendered
    assert "Showing 8 of 10 rejected candidates." in rendered
    assert "Use --output json for the complete structured record." in rendered
    assert "data/reports/analysis.db" in rendered


def test_scan_explain_uses_same_canonical_diagnostics_without_changing_cards() -> None:
    analysis = _payload()
    payload = {
        "total_symbol_count": 1,
        "filtered_symbol_count": 1,
        "displayed_symbol_count": 1,
        "total_analysis_count": 1,
        "retained_opportunity_count": 1,
        "displayed_opportunity_count": 1,
        "direction_filter": "both",
        "results": [analysis],
        "rejected_candidates": analysis["rejected_candidates"],
        "methodology_gate_mode": "enforce",
        "methodology_completeness": analysis["methodology_completeness"],
        "outcome_tracking": analysis["outcome_tracking"],
        "historical_calibration": analysis["historical_calibration"],
    }

    normal = render_scan(payload)
    explained = render_scan(payload, explain=True)

    assert "btc-current" not in normal
    assert "btc-current" in explained
    assert "Breakout retest · Current · Execute now" in normal
    assert "Breakout retest · Current · Execute now" in explained
    assert "Methodology enforcement" not in normal
    assert "Methodology enforcement" in explained
    assert "Opportunity portfolio" in explained
    assert "Rejected and suppressed candidates" in explained


def test_explain_reconciles_candidate_level_methodology_counts() -> None:
    payload = _payload()
    payload["phase5_diagnostics"] = {
        "methodology_candidate_routing": {
            "mode": "enforce",
            "input_candidate_count": 2,
            "strategy_decisions": [
                {"candidate_id": "one", "action": "allow"},
                {"candidate_id": "two", "action": "defer"},
                {"candidate_id": None, "action": "suppress"},
            ],
        }
    }

    rendered = render_analysis(payload, explain=True)

    assert "Candidates evaluated  2" in rendered
    assert "Allowed               1" in rendered
    assert "Deferred              1" in rendered
    assert "Suppressed            0" in rendered


def test_explain_does_not_report_serialized_trade_geometry_as_missing() -> None:
    payload = _payload()
    payload["methodology_completeness"] = {
        "unavailable_fields": [
            "setup_maturity",
            "confirmation_policy",
            "contradictions",
            "entry_opportunities",
            "invalidation",
            "targets",
            "duration",
            "confidence",
        ]
    }
    opportunity = payload["opportunity_portfolio"]["opportunities"][0]  # type: ignore[index]
    setup = opportunity["setup"]  # type: ignore[index]
    setup["confirmation_required"] = True  # type: ignore[index]
    setup["setup_expiry_seconds"] = 900  # type: ignore[index]
    setup["confidence_score"] = 75.0  # type: ignore[index]

    rendered = render_analysis(payload, explain=True)

    assert "Unavailable: Setup_maturity" in rendered
    for field in (
        "Confirmation_policy",
        "Contradictions",
        "Entry_opportunities",
        "Invalidation",
        "Targets",
        "Duration",
        "Confidence",
    ):
        assert f"Unavailable: {field}" not in rendered
