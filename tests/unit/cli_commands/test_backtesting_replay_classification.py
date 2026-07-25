"""Focused tests for replay classification and rejection aggregation."""

from __future__ import annotations

from apex.cli_commands.backtesting import (
    _classify_replay_trade_records,
    _geometry_rejection_summary,
    _replay_class_from_source,
)


def test_diagnostic_replay_records_are_explicitly_non_canonical() -> None:
    payload: dict[str, object] = {
        "shadow_replay": {
            "trades": [
                {
                    "canonical_portfolio": True,
                    "replay_class": "production",
                    "signal": {"replay_source": "geometry_rejected"},
                }
            ]
        }
    }

    _classify_replay_trade_records(
        payload,
        section="shadow_replay",
        replay_class="shadow",
    )

    section = payload["shadow_replay"]
    assert isinstance(section, dict)
    trades = section["trades"]
    assert isinstance(trades, list)
    assert trades[0]["canonical_portfolio"] is False
    assert trades[0]["replay_class"] == "shadow"


def test_geometry_rejection_summary_aggregates_codes_lanes_and_ratios() -> None:
    records: list[dict[str, object]] = [
        {
            "candidate_diagnostics": [
                {
                    "strategy": "first_pullback_continuation",
                    "geometry_rejection_codes": [
                        "stop_distance_below_cost_floor",
                        "tp1_exceeds_lane_horizon",
                    ],
                    "legacy_context_lane": "pullback_scalp",
                    "measured_geometry_lane": "nearby_structured",
                    "would_change_lane": True,
                    "would_change_geometry_result": False,
                    "geometry_audit": {
                        "gross_tp1_reward_to_risk": 2.0,
                        "net_tp1_reward_to_risk": 1.1,
                        "stop_to_cost_ratio": 0.5,
                        "target_to_cost_ratio": 2.5,
                        "tp1_distance_atr": 3.1,
                        "maximum_tp1_distance_atr": 3.0,
                    },
                },
                {
                    "strategy": "first_pullback_continuation",
                    "geometry_rejection_codes": ["stop_distance_below_cost_floor"],
                    "legacy_context_lane": "pullback_scalp",
                    "measured_geometry_lane": "pullback_scalp",
                    "would_change_lane": False,
                    "would_change_geometry_result": False,
                    "geometry_audit": {
                        "gross_tp1_reward_to_risk": 1.0,
                        "net_tp1_reward_to_risk": 0.2,
                        "stop_to_cost_ratio": 0.25,
                        "target_to_cost_ratio": 1.0,
                        "tp1_distance_atr": 1.0,
                        "maximum_tp1_distance_atr": 2.0,
                    },
                },
            ]
        }
    ]

    summary = _geometry_rejection_summary(records)

    assert summary["rejected_candidate_count"] == 2
    assert summary["rejection_code_counts"] == {
        "stop_distance_below_cost_floor": 2,
        "tp1_exceeds_lane_horizon": 1,
    }
    assert summary["strategy_counts"] == {"first_pullback_continuation": 2}
    assert summary["legacy_lane_counts"] == {"pullback_scalp": 2}
    assert summary["measured_lane_counts"] == {
        "nearby_structured": 1,
        "pullback_scalp": 1,
    }
    assert summary["would_change_lane_count"] == 1
    assert summary["would_change_geometry_result_count"] == 0
    averages = summary["averages"]
    assert isinstance(averages, dict)
    assert averages["gross_tp1_reward_to_risk"] == 1.5
    assert averages["net_tp1_reward_to_risk"] == 0.65
    assert averages["stop_to_cost_ratio"] == 0.375


def test_replay_source_classification_is_explicit_and_fail_closed() -> None:
    assert _replay_class_from_source("production") == "production"
    assert _replay_class_from_source("conditional_portfolio") == "conditional"
    assert _replay_class_from_source("opportunity_portfolio") == "opportunity"
    assert _replay_class_from_source("geometry_rejected") == "shadow"
    assert _replay_class_from_source("experimental") == "unknown"
