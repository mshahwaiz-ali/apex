from apex.cli_commands.backtesting import (
    _geometry_audit_diagnostics,
    _geometry_rejection_summary,
)


def test_geometry_audit_propagates_execution_cost_diagnostics() -> None:
    item = _geometry_audit_diagnostics(
        {
            "candidate_id": "trend_pullback:long:sample",
            "state": "reject",
            "available": True,
            "rejection_codes": ["tp1_below_lane_floor"],
            "diagnostics": {
                "selected_entry": 100.0,
                "executable_stop": 99.0,
                "tp1_price": 102.0,
                "execution_cost_profile": "limit",
                "cost_profile_reason": "resting_order_authorized",
                "expected_cost_pct": 0.09,
                "observed_spread_pct": 0.03,
            },
        }
    )

    assert item["execution_cost_profile"] == "limit"
    assert item["cost_profile_reason"] == "resting_order_authorized"
    assert item["expected_cost_pct"] == 0.09
    assert item["observed_spread_pct"] == 0.03


def test_geometry_summary_reports_cost_profile_distribution() -> None:
    summary = _geometry_rejection_summary(
        [
            {
                "candidate_diagnostics": [
                    {
                        "strategy": "trend_pullback",
                        "geometry_rejection_codes": ["tp1_below_lane_floor"],
                        "execution_cost_profile": "limit",
                        "cost_profile_reason": "resting_order_authorized",
                        "expected_cost_pct": 0.09,
                        "observed_spread_pct": 0.03,
                        "geometry_audit": {
                            "gross_tp1_reward_to_risk": 2.0,
                            "net_tp1_reward_to_risk": 1.1,
                        },
                    },
                    {
                        "strategy": "trend_pullback",
                        "geometry_rejection_codes": ["costs_eliminate_reward"],
                        "execution_cost_profile": "market",
                        "cost_profile_reason": "conservative_default",
                        "expected_cost_pct": 0.14,
                        "observed_spread_pct": 0.05,
                        "geometry_audit": {
                            "gross_tp1_reward_to_risk": 1.0,
                            "net_tp1_reward_to_risk": 0.2,
                        },
                    },
                ]
            }
        ]
    )

    assert summary["execution_cost_profile_counts"] == {"limit": 1, "market": 1}
    assert summary["cost_profile_reason_counts"] == {
        "conservative_default": 1,
        "resting_order_authorized": 1,
    }
    assert summary["averages"]["expected_cost_pct"] == 0.115
    assert summary["averages"]["observed_spread_pct"] == 0.04
