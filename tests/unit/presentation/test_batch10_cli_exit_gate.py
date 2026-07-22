from __future__ import annotations

from apex.presentation.operator_output import render_analysis, render_scan


def _setup(
    *,
    status: str = "READY_NOW",
    direction: str = "long",
    strategy: str = "breakout_continuation",
) -> dict[str, object]:
    return {
        "direction": direction,
        "strategy": strategy,
        "entry_status": status,
        "execution_allowed_now": status == "READY_NOW",
        "confidence_score": 84.0,
        "initial_risk_reward": 1.25,
        "runner_risk_reward": 3.1,
        "alignment_classification": "aligned",
        "entry": {
            "current_price": 100.0,
            "lower": 99.5,
            "upper": 100.5,
            "preferred": 100.0,
            "maximum_chase_price": 101.0,
            "distance_from_current": 0.004,
            "distance_unit": "fraction",
            "rationale": "CMP sits inside the accepted retest zone.",
            "maximum_chase_rationale": "Beyond this level the remaining reward compresses.",
        },
        "stop_loss": {
            "price": 97.0,
            "single_buffer_rationale": "Below structural invalidation plus execution buffer.",
        },
        "take_profits": (
            {"price": 103.0, "risk_reward": 1.25},
            {"price": 106.0, "risk_reward": 2.1},
            {"price": 109.0, "risk_reward": 3.1},
        ),
        "target_rationale": "TP1 de-risks; TP2 and TP3 follow higher-timeframe structure.",
        "quality_dimensions": {
            "setup_quality": 84.0,
            "execution_quality": 79.0,
            "continuation_quality": 76.0,
        },
        "evidence": (
            "Breakout acceptance persisted for two closed bars.",
            "Pullback volume contracted.",
        ),
        "contradictions": ("Depth imbalance is unavailable.",),
    }


def test_detailed_analysis_contains_all_remaining_batch10_sections() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "setup": _setup(),
        "nearby_alternative": _setup(status="WAIT_FOR_RETEST"),
        "opposite_follow_up": _setup(
            status="DEVELOPING",
            direction="short",
            strategy="failed_breakout_reversal",
        ),
        "multi_timeframe_map": {
            "5m": {"structure": "bullish", "momentum": "expanding"},
            "1h": {"structure": "bullish", "summary": "above reclaimed support"},
            "4h": "range_high",
        },
        "opportunity_collision": {"resolution": "coexist"},
        "opportunity_lifecycle": {"stage": "activated"},
        "runner_decision": {"decision": "hold_runner"},
        "rejected_candidates": (
            {
                "direction": "short",
                "strategy": "momentum_scalp",
                "reason": "Activation arrived after maximum chase.",
            },
        ),
        "methodology_completeness": {"unavailable_fields": ("liquidation_impulse",)},
    }

    output = render_analysis(payload, explain=True)

    for expected in (
        "Opportunity map",
        "Current opportunity",
        "Nearby alternative",
        "Opposite follow-up",
        "Multi-timeframe view",
        "5m: Bullish • Expanding",
        "Geometry rationale",
        "Entry rationale",
        "Stop rationale",
        "Target rationale",
        "Chase boundary",
        "Evidence and contradictions",
        "Support:",
        "Contradiction:",
        "Lifecycle and collision",
        "Collision:",
        "Runner:",
        "Rejected candidates",
        "Activation arrived after maximum chase.",
        "Data quality:",
        "liquidation_impulse",
    ):
        assert expected in output


def test_rejected_candidates_and_diagnostics_are_hidden_without_explain() -> None:
    payload = {
        "symbol": "BTCUSDT",
        "setup": _setup(),
        "opportunity_collision": {"resolution": "coexist"},
        "runner_decision": {"decision": "hold_runner"},
        "rejected_candidates": (
            {
                "direction": "short",
                "strategy": "momentum_scalp",
                "reason": "Rejected.",
            },
        ),
    }

    output = render_analysis(payload, explain=False)

    assert "Collision, runner, and lifecycle" not in output
    assert "Rejected candidates" not in output


def test_scan_compact_card_contains_complete_ranking_minimum_fields() -> None:
    payload = {
        "total_analysis_count": 1,
        "displayed_analysis_count": 1,
        "selected_setup_count": 1,
        "results": (
            {
                "symbol": "BTCUSDT",
                "setup": _setup(),
                "market_evidence": {"disposition": "degraded"},
            },
        ),
    }

    output = render_scan(payload)

    for expected in (
        "BTCUSDT",
        "Long",
        "Breakout",
        "Strategy",
        "Ready now",
        "CMP",
        "Entry",
        "Preferred",
        "Stop",
        "TP1",
        "TP2",
        "TP3",
        "Trade quality",
        "Execution quality",
        "Optional market evidence is incomplete",
    ):
        assert expected in output


def test_scan_preserves_tp1_tp2_tp3_values() -> None:
    payload = {
        "total_analysis_count": 1,
        "displayed_analysis_count": 1,
        "selected_setup_count": 1,
        "results": ({"symbol": "BTCUSDT", "setup": _setup()},),
    }

    output = render_scan(payload)

    assert "103" in output
    assert "106" in output
    assert "109" in output


def test_no_cmp_entry_is_distinct_from_no_setup() -> None:
    pending = _setup(status="WAIT_FOR_RETEST")
    payload = {
        "total_analysis_count": 2,
        "displayed_analysis_count": 2,
        "selected_setup_count": 0,
        "results": (
            {"symbol": "BTCUSDT", "setup": pending},
            {"symbol": "ETHUSDT", "reasons": ("No valid setup formed.",)},
        ),
    }

    output = render_scan(payload)

    assert "Conditional monitoring" in output
    assert "BTCUSDT" in output
    assert "No current trade" in output
    assert "ETHUSDT" in output
    assert "No valid setup formed." in output


def test_analysis_does_not_invent_missing_detailed_sections() -> None:
    output = render_analysis({"symbol": "BTCUSDT", "setup": _setup()})

    assert "Multi-timeframe map" not in output
    assert "Rejected candidates" not in output
