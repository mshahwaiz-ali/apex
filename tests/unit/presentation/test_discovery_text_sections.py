"""Tests for compact operator-facing discovery text."""

from __future__ import annotations

from apex.presentation.discovery_output import render_discovery_analysis, render_discovery_scan


def _setup_payload() -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "result_group": "actionable",
        "reasons": ("structure and participation support the setup",),
        "candidate_count": 3,
        "setup": {
            "direction": "long",
            "strategy": "trend_pullback",
            "entry_status": "READY_NOW",
            "confidence_score": 71.0,
            "entry": {
                "current_price": 100.0,
                "lower": 99.0,
                "upper": 101.0,
                "preferred": 100.0,
                "maximum_chase_price": 102.0,
            },
            "stop_loss": {
                "price": 97.5,
                "distance_pct": 2.5,
                "quality_band": "acceptable",
            },
            "take_profits": (
                {
                    "price": 104.0,
                    "risk_reward": 1.6,
                    "partial_close_pct": 50.0,
                },
            ),
            "management_policies": (),
            "warnings": (),
        },
        "methodology_selected_entry_semantics": {
            "selected_kind": "immediate_entry",
            "currently_executable": True,
            "future_trigger_required": False,
            "selection_reason": "entry is inside the selected structural zone",
        },
        "methodology_candlestick_evidence": (
            {
                "pattern_id": "hammer",
                "pattern_direction": "bullish",
                "completion_state": "completed",
                "context_note": "timing evidence only",
            },
        ),
    }


def test_analysis_text_exposes_entry_and_candlestick_sections() -> None:
    rendered = render_discovery_analysis(_setup_payload())

    assert "Why This Entry" in rendered
    assert "Candlestick Evidence" in rendered
    assert "Hammer" in rendered
    assert "Executable now" in rendered


def test_analysis_text_explains_independent_no_trade_theses() -> None:
    rendered = render_discovery_analysis(
        {
            "symbol": "SXT/USDT",
            "reasons": ("all candidates scored below their configured approval thresholds",),
            "candidate_count": 2,
            "setup": None,
            "developing_setup": None,
            "focused_analysis": {
                "market_outlook": {
                    "regime": "range",
                    "market_condition": "compressed",
                    "primary_structure": "range",
                    "setup_structure": "NO_BREAK",
                    "entry_timeframe": "5m",
                    "volatility": "compressed",
                    "participation": "normal",
                    "current_location": "support 0.0074, resistance 0.0077",
                },
                "directional_assessment": {
                    "preferred_side": "none",
                    "long_state": "rejected",
                    "short_state": "developing",
                    "confidence_label": "Low",
                    "reason": "neither side is executable",
                },
                "long_thesis": {
                    "state": "rejected",
                    "primary_strategy": "breakout_continuation",
                    "score": 56.7,
                    "approval_threshold": 58.0,
                    "score_shortfall": 1.3,
                    "candidate_outcome": "rejected_below_score_threshold",
                    "summary": "long breakout continuation is not approved",
                    "blockers": ("rule-based quality is below threshold",),
                    "activation_conditions": ("5m candle closes above resistance",),
                    "invalidation_conditions": ("setup invalidates below support",),
                },
                "short_thesis": {
                    "state": "developing",
                    "primary_strategy": "breakout_retest",
                    "score": 60.0,
                    "approval_threshold": 58.0,
                    "score_shortfall": 0.0,
                    "candidate_outcome": "accepted",
                    "summary": "short is developing; retest required",
                    "blockers": ("retest confirmation is incomplete",),
                    "activation_conditions": ("support breaks and retest fails",),
                    "invalidation_conditions": ("reclaim above failed support",),
                },
                "watch_plan": ("avoid forcing direction",),
            },
        }
    )

    assert "Market Outlook" in rendered
    assert "Directional Assessment" in rendered
    assert "Long Assessment" in rendered
    assert "Short Assessment" in rendered
    assert "Required threshold" in rendered
    assert "Watch Next" in rendered


def test_scan_text_exposes_discovery_lanes() -> None:
    rendered = render_discovery_scan(
        {
            "total_analysis_count": 1,
            "displayed_analysis_count": 1,
            "selected_setup_count": 0,
            "actionable_count": 0,
            "developing_count": 0,
            "unavailable_count": 0,
            "no_trade_count": 0,
            "long_candidate_count": 0,
            "short_candidate_count": 0,
            "status_counts": {},
            "actionable_setups": (),
            "developing_setups": (),
            "unavailable_setups": (),
            "no_trade_results": (),
            "screening": {
                "candidates": (
                    {
                        "symbol": "BTC/USDT",
                        "discovery_lanes": (
                            {
                                "lane": "trend_continuation",
                                "score": 74.0,
                                "reason": "directional persistence remains usable",
                            },
                        ),
                    },
                )
            },
        }
    )

    assert "Discovery Lanes" in rendered
    assert "Trend continuation" in rendered
