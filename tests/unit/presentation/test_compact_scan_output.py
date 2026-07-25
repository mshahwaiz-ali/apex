from __future__ import annotations

from apex.presentation.compact_scan_output import render_compact_scan


def _setup(symbol: str, confidence: float, preferred: float) -> dict[str, object]:
    return {
        "symbol": symbol,
        "setup": {
            "symbol": symbol,
            "direction": "long",
            "strategy": "trend_pullback",
            "entry_status": "pullback_preferred",
            "confidence_score": confidence,
            "execution_allowed_now": False,
            "execution_authority": "conditional_future",
            "entry_mode": "retest",
            "entry": {
                "current_price": preferred + 0.01,
                "lower": preferred - 0.001,
                "upper": preferred + 0.001,
                "preferred": preferred,
                "maximum_chase_price": preferred + 0.002,
            },
            "stop_loss": {"price": preferred - 0.01},
            "take_profits": [
                {
                    "price": preferred + 0.03,
                    "risk_reward": 3.0,
                    "net_risk_reward": 2.4,
                }
            ],
            "quality_dimensions": {
                "setup_quality": confidence,
                "execution_quality": 55.0,
                "target_quality": 75.0,
                "overall_trade_quality": confidence - 5.0,
            },
            "conditional_plan": {
                "trigger": {
                    "type": "retest_hold",
                    "level": preferred,
                    "condition": "price retests and holds the entry zone",
                    "confirmation_timeframe": "5m",
                },
                "pre_entry_invalidation": {"price": preferred - 0.005},
                "recommended_order_intent": "alert_only",
                "reason_not_executable_now": "wait for the retest hold",
            },
            "warnings": ["active-candle evidence is provisional"],
        },
    }


def test_scan_uses_analyze_style_cards_sorted_by_confidence() -> None:
    payload = {
        "generated_at": "2026-07-25T00:21:31+00:00",
        "attempted_symbol_count": 2,
        "total_analysis_count": 2,
        "displayed_symbol_count": 2,
        "results": [
            _setup("LOW/USDT", 61.0, 1.0),
            _setup("HIGH/USDT", 84.0, 2.0),
        ],
    }

    output = render_compact_scan(payload)

    assert "Ranking" in output
    assert "Highest published confidence first" in output
    assert "SETUP PLAN 1 • FUTURE RETEST • HIGH/USDT" in output
    assert "SETUP PLAN 2 • FUTURE RETEST • LOW/USDT" in output
    assert output.index("HIGH/USDT") < output.index("LOW/USDT")
    assert "ENTRY" in output
    assert "RISK" in output
    assert "TARGETS" in output
    assert "SETUP" in output


def test_scan_explain_reuses_analyze_explanation_fields() -> None:
    payload = {
        "generated_at": "2026-07-25T00:21:31+00:00",
        "attempted_symbol_count": 1,
        "total_analysis_count": 1,
        "displayed_symbol_count": 1,
        "results": [_setup("HIGH/USDT", 84.0, 2.0)],
    }

    output = render_compact_scan(payload, explain=True)

    assert "WHY THIS TRADE" in output
    assert "Setup quality" in output
    assert "Execution quality" in output
    assert "Target quality" in output
    assert "WARNINGS" in output
