from __future__ import annotations

from apex.presentation.discovery_output import render_discovery_analysis


def test_methodology_details_are_visible_without_raw_internal_dump() -> None:
    payload = {
        "symbol": "TEST/USDT",
        "result_group": "ready",
        "reasons": ["structure and participation support continuation"],
        "setup": {
            "direction": "long",
            "strategy": "trend_pullback",
            "entry_status": "READY_NOW",
            "confidence_score": 78.0,
            "trader_headline": "Strong setup — executable now",
            "execution_allowed_now": True,
            "setup_validity": "30 minutes",
            "setup_expiry_reason": "strategy and entry-mode validity policy",
            "quality_dimensions": {
                "setup_quality": 84.0,
                "execution_quality": 76.0,
                "target_quality": 72.0,
                "risk_quality": 81.0,
                "overall_trade_quality": 79.0,
            },
            "entry": {
                "lower": 99.5,
                "upper": 100.5,
                "preferred": 100.0,
                "current_price": 100.1,
                "maximum_chase_price": 100.8,
            },
            "alternative_entry_opportunities": [
                {
                    "lower": 98.5,
                    "upper": 99.0,
                    "preferred": 98.75,
                    "maximum_chase_price": 99.2,
                }
            ],
            "stop_loss": {
                "price": 97.5,
                "distance_pct": 2.5,
                "quality_band": "strong",
                "stop_type": "structural",
                "single_buffer_rationale": "single 0.25 ATR structural-noise buffer",
            },
            "take_profits": [
                {
                    "price": 102.5,
                    "risk_reward": 1.0,
                    "partial_close_pct": 40.0,
                    "target_type": "partial",
                    "purpose": "risk-reduction partial",
                },
                {
                    "price": 106.0,
                    "risk_reward": 2.4,
                    "partial_close_pct": 60.0,
                    "target_type": "structural",
                    "purpose": "primary structural objective",
                },
            ],
            "management_policies": [],
            "warnings": [],
        },
    }

    rendered = render_discovery_analysis(payload)

    assert "Strong setup — executable now" in rendered
    assert "Setup quality" in rendered
    assert "Execution allowed now" in rendered
    assert "Alternative Entry Opportunities" in rendered
    assert "single 0.25 ATR structural-noise buffer" in rendered
    assert "risk-reduction partial" in rendered
    assert "primary structural objective" in rendered
    assert "30 minutes" in rendered
