"""Tests for native methodology fields derived from selected setups."""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application.discovery_analysis import _build_native_methodology_snapshot
from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.methodology_contracts import ConfidenceBasis, EntryOpportunityType
from apex.strategies.context import (
    FeatureSnapshot,
    StrategyContext,
    TimeframeContext,
    TimeframeRole,
)
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _context() -> StrategyContext:
    frame = TimeframeContext(
        timeframe="15m",
        role=TimeframeRole.SETUP,
        current_price=100.0,
        features=FeatureSnapshot(atr=2.0),
        structure=SimpleNamespace(),
        liquidity=SimpleNamespace(),
    )
    return StrategyContext(symbol="BTCUSDT", frames=(frame,))


def _setup() -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.TREND_PULLBACK,
        entry_status=EntryStatus.READY_NOW,
        decision_time=datetime(2026, 1, 1, tzinfo=UTC),
        candidate_id="candidate-1",
        confidence_score=72.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=97.0,
            distance=3.0,
            distance_pct=3.0,
            rationale=("pullback swing low",),
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=105.0,
                reward=5.0,
                risk_reward=1.67,
                rationale=("prior swing high",),
                partial_close_pct=100.0,
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.BREAKEVEN,
                trigger="TP1 touched",
                action="move stop to breakeven",
                rationale=("reduce risk after first target",),
            ),
        ),
    )


def test_selected_setup_populates_native_methodology_geometry() -> None:
    snapshot = _build_native_methodology_snapshot(
        _setup(),
        context=_context(),
        evidence=(),
        contradictions=(),
        no_trade_reason=None,
    )

    assert snapshot.direction is TradeDirection.LONG
    assert snapshot.entry_opportunities[0].kind is EntryOpportunityType.IMMEDIATE
    assert snapshot.selected_entry is not None
    assert snapshot.invalidation is not None
    assert snapshot.targets[0].source == "prior swing high"
    assert snapshot.duration is not None
    assert snapshot.confidence is not None
    assert snapshot.confidence.basis is ConfidenceBasis.RULE_BASED
    assert snapshot.executable is True
