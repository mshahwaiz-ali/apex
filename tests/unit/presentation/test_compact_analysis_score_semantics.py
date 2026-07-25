from __future__ import annotations

from apex.presentation.compact_analysis_output import render_compact_analysis


def test_analysis_separates_selection_score_from_trade_quality() -> None:
    payload = {
        "symbol": "VANA/USDT",
        "generated_at": "2026-07-25T10:45:22+00:00",
        "opportunity_portfolio": {
            "cmp": 1.295,
            "decision": "conditional_future",
            "nearby_opportunities": [
                {
                    "final_score": 32.6,
                    "setup": {
                        "symbol": "VANA/USDT",
                        "direction": "long",
                        "strategy": "breakout_continuation",
                        "entry_status": "missed_entry",
                        "confidence_score": 32.6,
                        "execution_allowed_now": False,
                        "execution_authority": "monitor_only",
                        "entry_mode": "retest",
                        "entry": {
                            "current_price": 1.295,
                            "lower": 1.280,
                            "upper": 1.280,
                            "preferred": 1.280,
                            "maximum_chase_price": 1.282,
                        },
                        "stop_loss": {"price": 1.274},
                        "take_profits": [
                            {
                                "price": 1.297,
                                "risk_reward": 2.2,
                                "net_risk_reward": 1.92,
                            }
                        ],
                        "quality_dimensions": {
                            "setup_quality": 79.9,
                            "execution_quality": 20.0,
                            "target_quality": 59.7,
                            "risk_quality": 55.4,
                            "overall_trade_quality": 53.8,
                        },
                        "conditional_plan": {
                            "trigger": {
                                "type": "retest_hold",
                                "level": 1.280,
                                "confirmation_timeframe": "5m",
                                "condition": "price retests and holds the entry zone",
                            },
                            "pre_entry_invalidation": {"price": 1.278},
                            "recommended_order_intent": "alert_only",
                            "reason_not_executable_now": "current price is beyond entry geometry",
                        },
                    },
                }
            ],
        },
    }

    output = render_compact_analysis(payload, explain=True)

    assert "Selection score" in output
    assert "32.6/100" in output
    assert "Overall trade quality" in output
    assert "53.8/100" in output
    assert "Historical confidence" in output
    assert "Not calibrated" in output
    assert "Risk quality" in output
    assert "55.4/100" in output
    assert "Confidence" not in output
