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
                "risk_quality": 68.0,
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


def _blocked_setup(
    symbol: str,
    confidence: float,
    preferred: float,
    net_r: float,
) -> dict[str, object]:
    item = _setup(symbol, confidence, preferred)
    setup = item["setup"]
    assert isinstance(setup, dict)
    setup.pop("conditional_plan")
    targets = setup["take_profits"]
    assert isinstance(targets, list)
    target = targets[0]
    assert isinstance(target, dict)
    target["net_risk_reward"] = net_r
    setup["warnings"] = [
        "Confirmation-required setup has no post-confirmation execution room "
        "while preserving minimum net reward-to-risk."
    ]
    return item


def _single_spaced(value: str) -> str:
    return " ".join(value.split())


def test_scan_uses_analyze_style_cards_sorted_by_selection_score() -> None:
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
    compact = _single_spaced(output)

    assert "Ranking" in output
    assert "Actionability first; selection score within each actionable lane" in compact
    assert "Future / re-entry plans 2" in compact
    assert "Activation blocked 0" in compact
    assert "SETUP PLAN 1 • FUTURE RETEST • HIGH/USDT" in output
    assert "SETUP PLAN 2 • FUTURE RETEST • LOW/USDT" in output
    assert output.index("HIGH/USDT") < output.index("LOW/USDT")
    assert "Selection score" in output
    assert "Overall trade quality" in output
    assert "Historical confidence" in output
    assert "Confidence" not in output
    assert "ENTRY" in output
    assert "RISK" in output
    assert "TARGETS" in output
    assert "SETUP" in output


def test_blocked_plans_are_counted_separately_and_ranked_by_remaining_net_r() -> None:
    payload = {
        "generated_at": "2026-07-25T00:21:31+00:00",
        "attempted_symbol_count": 3,
        "total_analysis_count": 3,
        "displayed_symbol_count": 3,
        "results": [
            _blocked_setup("LOW-R/USDT", 90.0, 1.0, 0.15),
            _setup("FUTURE/USDT", 20.0, 2.0),
            _blocked_setup("HIGH-R/USDT", 40.0, 3.0, 1.01),
        ],
    }

    output = render_compact_scan(payload)
    compact = _single_spaced(output)

    assert "Future / re-entry plans 1" in compact
    assert "Activation blocked 2" in compact
    assert output.index("FUTURE/USDT") < output.index("HIGH-R/USDT")
    assert output.index("HIGH-R/USDT") < output.index("LOW-R/USDT")


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
    assert "Risk quality" in output
    assert "Overall trade quality" in output
    assert "WARNINGS" in output
