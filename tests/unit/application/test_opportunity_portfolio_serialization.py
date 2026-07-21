from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoveryAssessment,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    opportunity_portfolio_payload,
    portfolio_from_legacy_assessment,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def test_legacy_portfolio_payload_is_additive_and_deterministic() -> None:
    setup = DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW,
        decision_time=NOW,
        candidate_id="candidate-1",
        confidence_score=72.0,
        entry=ActionableEntry(99.0, 101.0, 100.0, 100.0, 102.0, True),
        stop_loss=StopLoss(97.0, 3.0, 3.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 106.0, 6.0, 2.0, ("liquidity",)),),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=True,
    )
    assessment = DiscoveryAssessment(
        symbol="BTCUSDT",
        decision_time=NOW,
        setup=setup,
    )

    portfolio = portfolio_from_legacy_assessment(
        assessment,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    payload = opportunity_portfolio_payload(portfolio)

    assert payload["analysis_mode"] == "analyze_full"
    assert payload["opportunity_count"] == 1
    current_long = payload["current_long"]
    assert isinstance(current_long, dict)
    ranking = current_long.pop("ranking")
    rank_score = current_long.pop("rank_score")
    assert ranking["rank_score"] == rank_score
    assert current_long == {
        "opportunity_id": "candidate-1",
        "sequence_role": "current",
        "lane": "cmp_scalp",
        "direction": "long",
        "strategy": StrategyType.BREAKOUT_CONTINUATION.value,
        "strategy_family": StrategyType.BREAKOUT_CONTINUATION.canonical_family.value,
        "entry_status": EntryStatus.READY_NOW.value,
        "execution_allowed_now": True,
        "cmp": 100.0,
        "cmp_actionability": {
            "state": "executable_at_cmp",
            "source_entry_status": "READY_NOW",
            "execution_allowed_now": True,
            "location_state": "inside_entry_zone",
        },
        "actionability_consistency": {
            "is_consistent": True,
            "codes": [],
            "source_entry_status": "READY_NOW",
            "execution_allowed_now": True,
            "location_state": "inside_entry_zone",
            "beyond_maximum_chase": False,
            "sequence_role": "current",
        },
        "actionability_state": {
            "state": "execute_now",
            "basis": "executable_inside_zone",
            "source_entry_status": "READY_NOW",
            "execution_allowed_now": True,
            "location_state": "inside_entry_zone",
            "sequence_role": "current",
            "issues": [],
            "has_blocking_issue": False,
            "is_legacy_projection": True,
        },
        "setup_existence": {
            "state": "structurally_valid",
            "source_entry_status": "READY_NOW",
            "setup_exists": True,
        },
        "cmp_entry_assessment": {
            "state": "available_now",
            "execution_allowed_now": True,
            "location_state": "inside_entry_zone",
            "beyond_maximum_chase": False,
            "setup_existence_state": "structurally_valid",
        },
        "entry_boundary_consistency": {
            "is_consistent": True,
            "codes": [],
            "ideal_entry_inside_zone": True,
            "maximum_chase_directionally_valid": True,
            "maximum_chase_equals_ideal_entry": False,
            "beyond_maximum_chase": False,
            "source_entry_status": "READY_NOW",
        },
        "stale_trigger": {
            "state": "not_configured",
            "codes": [],
            "evaluated_at": NOW.isoformat(),
            "decision_time": NOW.isoformat(),
            "age_seconds": 0.0,
            "setup_expiry_seconds": None,
            "setup_expiry_bars": None,
            "setup_expiry_reason": "",
            "execution_allowed_now": True,
            "is_stale": False,
        },
        "cmp_distance": {
            "zone_position": "inside_entry_zone",
            "location_state": "inside_entry_zone",
            "distance_to_entry_zone": 0.0,
            "distance_to_entry_zone_pct": 0.0,
            "distance_to_ideal_entry": 0.0,
            "distance_to_ideal_entry_pct": 0.0,
            "distance_to_maximum_chase": 2.0,
            "distance_to_maximum_chase_pct": 2.0,
            "beyond_maximum_chase": False,
        },
        "entry_zone": {
            "lower": 99.0,
            "upper": 101.0,
            "preferred": 100.0,
            "maximum_chase": 102.0,
        },
        "stop": 97.0,
        "targets": [{"label": "TP1", "price": 106.0, "risk_reward": 2.0}],
    }
    assert payload["current_short"] is None
    assert payload["nearby_long"] is None
    assert payload["follow_up_opportunities"] == []
    assert list(payload["best_opportunities_by_lane"]) == ["cmp_scalp"]
