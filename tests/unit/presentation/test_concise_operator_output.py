from __future__ import annotations

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
    assert "Entry  74.742" in output
    assert "Stop loss" in output
    assert "TP1" in output
    assert "Selection Limitations" not in output
    assert "Evidence Independence" not in output
    assert "Ranking Integrity" not in output
