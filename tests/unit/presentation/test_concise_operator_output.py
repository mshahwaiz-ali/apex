from __future__ import annotations

from apex.presentation.compact_analysis_output import render_compact_analysis
from apex.presentation.discovery_output import render_discovery_analysis
from apex.presentation.methodology_selected_entry_output import (
    render_discovery_analysis as render_final_analysis,
)


def _payload() -> dict[str, object]:
    return {
        "symbol": "SOL/USDT",
        "result_group": "developing",
        "candidate_count": 1,
        "reasons": ["trend and structure support a conditional short"],
        "setup": {
            "direction": "short",
            "strategy": "breakout_retest",
            "entry_status": "pullback_preferred",
            "confidence_score": 52.8,
            "entry": {
                "current_price": 74.68,
                "lower": 74.7423,
                "upper": 74.7423,
                "preferred": 74.7423,
                "maximum_chase_price": 73.7838,
            },
            "stop_loss": {
                "price": 74.8339,
                "distance_pct": 0.12,
                "quality_band": "acceptable",
            },
            "take_profits": [
                {
                    "price": 74.46,
                    "risk_reward": 3.08,
                    "partial_close_pct": 100.0,
                }
            ],
            "management_policies": [],
            "warnings": ["active-candle evidence is provisional"],
        },
        "methodology_selected_entry_semantics": {
            "selected_kind": "pullback_entry",
            "currently_executable": False,
            "future_trigger_required": True,
            "selection_reason": "retest remains pending",
        },
        "methodology_target_feasibility_semantics": {
            "interpretation": "gross target geometry is available",
            "gross_geometry_available": True,
            "costs_available": False,
        },
    }


def _conditional_payload() -> dict[str, object]:
    return {
        "symbol": "BANK/USDT",
        "generated_at": "2026-07-25T00:01:08+00:00",
        "opportunity_portfolio": {
            "cmp": 0.3031,
            "decision": "nearby_setup_available",
            "opportunities": [
                {
                    "setup": {
                        "direction": "long",
                        "strategy": "trend_pullback",
                        "entry_status": "pullback_preferred",
                        "confidence_score": 32.6,
                        "execution_allowed_now": False,
                        "execution_authority": "monitor_only",
                        "entry_mode": "retest",
                        "entry": {
                            "current_price": 0.3031,
                            "lower": 0.3008,
                            "upper": 0.3015,
                            "preferred": 0.3012,
                            "maximum_chase_price": 0.3020,
                        },
                        "stop_loss": {"price": 0.2996},
                        "take_profits": [
                            {
                                "price": 0.3062,
                                "risk_reward": 3.13,
                            }
                        ],
                        "quality_dimensions": {
                            "setup_quality": 38.8,
                            "execution_quality": 50.0,
                            "target_quality": 82.8,
                        },
                        "conditional_plan": {
                            "trigger": {
                                "type": "retest_hold",
                                "level": 0.3012,
                                "condition": "price retests and demonstrates acceptance",
                                "confirmation_timeframe": "5m",
                            },
                            "pre_entry_invalidation": {"price": 0.3004},
                            "recommended_order_intent": "alert_only",
                            "reason_not_executable_now": (
                                "price has not reached the preferred pullback zone"
                            ),
                            "expiry": {"bars": 4, "reason": "retest window"},
                            "geometry": {
                                "stop_basis": "structural_invalidation_buffered",
                                "targets_basis": "strategy_supplied_targets",
                            },
                        },
                        "warnings": [
                            "decision-frame momentum is fully opposed",
                        ],
                    }
                }
            ],
        },
    }


def test_exact_entry_is_not_labeled_as_zone() -> None:
    output = render_discovery_analysis(_payload())
    assert "Entry price" in output
    assert "Entry zone" not in output


def test_cost_warning_is_visible() -> None:
    output = render_discovery_analysis(_payload())
    assert "fees and slippage are not included" in output


def test_final_renderer_uses_compact_trade_card_without_internal_appendices() -> None:
    output = render_final_analysis(_payload())

    assert "APEX ANALYSIS • SOL/USDT" in output
    assert "┌─ TRADE 1 • SOL/USDT • SHORT • Breakout retest" in output
    assert "Entry zone" not in output
    assert "74.742" in output
    assert "Stop loss" in output
    assert "TP1" in output
    assert "Selection Limitations" not in output
    assert "Evidence Independence" not in output
    assert "Ranking Integrity" not in output


def test_conditional_retest_is_labeled_and_explained_as_future_setup() -> None:
    output = render_compact_analysis(_conditional_payload(), explain=True)

    assert "SETUP PLAN 1 • FUTURE RETEST" in output
    assert "Future retest - hold required" in output
    assert "Retest hold at 0.3012 on 5m" in output
    assert "Pre-entry invalidation" in output
    assert "Post-entry stop" in output
    assert "Maximum chase" in output
    assert "Gross / net R" in output
    assert "3.13R gross" in output
    assert "Additional targets" in output
    assert "Not published - no verified structure" in output
