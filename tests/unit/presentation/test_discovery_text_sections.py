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

    assert "Trade plan" in rendered
    assert "Why this trade" in rendered
    assert "Current price" in rendered
    assert "Preferred entry" in rendered
    assert "Stop" in rendered
    assert "TP1" in rendered


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
                "long_thesis": {},
                "short_thesis": {},
                "watch_plan": ("avoid forcing direction",),
            },
        }
    )

    assert "NO TRADE" in rendered
    assert "Market context" in rendered
    assert "Range" in rendered
    assert "Compressed" in rendered
    assert "Support 0.0074, resistance 0.0077" in rendered


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
        },
        explain=True,
    )

    assert "Shortlist evidence" in rendered
    assert "BTC/USDT" in rendered


def _developing_conditional_payload() -> dict[str, object]:
    base = _setup_payload()
    setup = dict(base["setup"])
    setup.update(
        {
            "entry_status": "PULLBACK_PREFERRED",
            "execution_allowed_now": False,
            "setup_validity": "15 minutes",
            "setup_expiry_seconds": 900,
            "setup_expiry_bars": 6,
            "setup_expiry_reason": "candidate activation window",
            "conditional_plan": {
                "trigger": {
                    "type": "price_touch",
                    "level": 100.0,
                    "condition": (
                        "price enters the predefined entry zone and the setup "
                        "is revalidated before order placement"
                    ),
                    "confirmation_timeframe": "5m",
                },
                "pre_entry_invalidation": {
                    "price": 98.0,
                    "condition": (
                        "price reaches or closes below structural invalidation before activation"
                    ),
                    "rationale": ("raw thesis invalidation",),
                },
                "conditional_order_eligible": False,
                "recommended_order_intent": "limit",
                "reason_not_executable_now": ("price has not reached the preferred pullback zone"),
                "expiry": {
                    "seconds": 900,
                    "bars": 6,
                    "reason": "candidate activation window",
                    "validity": "15 minutes",
                },
                "geometry": {
                    "geometry_basis": "candidate_entry_zone",
                    "entry_source": "strategy_generated_pullback_reference",
                    "trigger_matches_preferred_entry": True,
                    "stop_basis": ("structural_invalidation_buffered_from_candidate_entry"),
                    "targets_basis": "strategy_supplied_structural_targets",
                    "geometry_is_trigger_relative": True,
                },
            },
        }
    )
    return {
        "symbol": "BTCUSDT",
        "result_group": "developing_setup",
        "reasons": ("price has not reached the preferred pullback zone",),
        "candidate_count": 1,
        "setup": None,
        "developing_setup": setup,
    }


def test_pending_setup_renders_conditional_entry_plan() -> None:
    rendered = render_discovery_analysis(_developing_conditional_payload())

    assert "Conditional entry plan" in rendered
    assert "Price touch" in rendered
    assert "Trigger level" in rendered
    assert "Pre-entry invalidation" in rendered
    assert "Order intent" in rendered
    assert "Limit" in rendered
    assert "Resting order authorized" in rendered
    assert "No" in rendered
    assert "15 minutes" in rendered
    assert "candidate activation window" in rendered


def test_developing_scan_renders_conditional_summary() -> None:
    result = _developing_conditional_payload()
    rendered = render_discovery_scan(
        {
            "total_analysis_count": 1,
            "displayed_analysis_count": 1,
            "selected_setup_count": 0,
            "actionable_count": 0,
            "developing_count": 1,
            "unavailable_count": 0,
            "no_trade_count": 0,
            "long_candidate_count": 1,
            "short_candidate_count": 0,
            "status_counts": {"PULLBACK_PREFERRED": 1},
            "actionable_setups": (),
            "developing_setups": (result,),
            "unavailable_setups": (),
            "no_trade_results": (),
        }
    )

    assert "Trigger" in rendered
    assert "Price touch" in rendered
    assert "Pre-entry invalidation" in rendered
    assert "Order intent" in rendered
    assert "Limit" in rendered


def test_executable_setup_omits_conditional_entry_plan() -> None:
    rendered = render_discovery_analysis(_setup_payload())

    assert "Conditional entry plan" not in rendered
