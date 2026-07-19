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
    assert payload["current_long"] == {
        "opportunity_id": "candidate-1",
        "sequence_role": "current",
        "direction": "long",
        "strategy": StrategyType.BREAKOUT_CONTINUATION.value,
        "strategy_family": StrategyType.BREAKOUT_CONTINUATION.canonical_family.value,
        "entry_status": EntryStatus.READY_NOW.value,
        "execution_allowed_now": True,
        "cmp": 100.0,
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
