from __future__ import annotations

from apex.presentation.actionable_plan import (
    hydrate_actionable_setup,
    plan_completeness,
    plan_lane,
)


def test_pullback_plan_recovers_geometry_and_builds_concrete_trigger() -> None:
    opportunity = {
        "symbol": "CHILLGUY/USDT",
        "cmp": 0.01115,
        "developing_setup": {
            "strategy": "compression_expansion",
            "direction": "long",
            "entry_status": "PULLBACK_PREFERRED",
            "confidence_score": 52.3,
        },
        "diagnostics": {
            "entry_zone": {
                "lower": 0.01090,
                "upper": 0.01100,
                "preferred": 0.01095,
                "maximum_chase_price": 0.01102,
            },
            "post_entry_stop": {"price": 0.01070},
            "confirmation_timeframe": "5m",
        },
    }

    setup = hydrate_actionable_setup(opportunity)

    assert setup["entry"] == {
        "lower": 0.01090,
        "upper": 0.01100,
        "preferred": 0.01095,
        "maximum_chase_price": 0.01102,
        "current_price": 0.01115,
    }
    assert setup["stop_loss"] == {"price": 0.01070}
    plan = setup["conditional_plan"]
    assert plan["trigger"]["type"] == "retest_hold"
    assert plan["trigger"]["level"] == 0.01095
    assert plan["trigger"]["confirmation_timeframe"] == "5m"
    assert plan["pre_entry_invalidation"]["price"] == 0.01070
    assert "do not chase" in plan["reason_not_executable_now"].lower()
    assert plan_completeness(setup) == 8
    assert plan_lane(setup) == 4


def test_missed_entry_becomes_lower_priority_complete_reentry_plan() -> None:
    opportunity = {
        "symbol": "HYPE/USDT",
        "current_price": 32.0,
        "setup": {
            "strategy": "trend_pullback",
            "direction": "long",
            "entry_status": "MISSED_ENTRY",
            "confidence_score": 70.0,
        },
        "re_entry_zone": {
            "lower": 30.8,
            "upper": 31.2,
            "preferred": 31.0,
        },
        "stop_loss": {"price": 30.2},
    }

    setup = hydrate_actionable_setup(opportunity)

    assert setup["entry"]["current_price"] == 32.0
    assert setup["entry"]["preferred"] == 31.0
    assert setup["conditional_plan"]["trigger"]["type"] == "retest_hold"
    assert "original entry was missed" in setup["conditional_plan"][
        "reason_not_executable_now"
    ].lower()
    assert plan_completeness(setup) == 8
    assert plan_lane(setup) == 3


def test_incomplete_high_confidence_summary_ranks_below_actionable_plan() -> None:
    incomplete = hydrate_actionable_setup(
        {
            "setup": {
                "entry_status": "PULLBACK_PREFERRED",
                "confidence_score": 90.0,
            }
        }
    )
    actionable = hydrate_actionable_setup(
        {
            "cmp": 100.0,
            "setup": {
                "entry_status": "PULLBACK_PREFERRED",
                "confidence_score": 40.0,
                "entry": {"lower": 98.0, "upper": 99.0, "preferred": 98.5},
                "stop_loss": {"price": 97.0},
            },
        }
    )

    assert plan_lane(incomplete) == 1
    assert plan_lane(actionable) == 4
