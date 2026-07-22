from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application.discovery_contracts import (
    ActionableEntry,
    ActivationTrigger,
    ActivationTriggerType,
    ConditionalExecutionPlan,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    PreEntryInvalidation,
    RecommendedOrderIntent,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import OpportunityLane, SequenceRole
from apex.cli_commands import backtesting
from apex.domain.methodology_contracts import (
    ContextState,
    ContinuationState,
    ExecutionState,
    HoldingHorizon,
    LayeredStateSnapshot,
    RelationshipSeverity,
    RiskCondition,
    ScoreDimensions,
    SetupState,
    StructuralBias,
    TimeframeRelationship,
)
from apex.strategies import StrategyType, TradeDirection
from apex.strategies.entry_status import EntryStatus


def _setup(
    candidate_id: str,
    *,
    execution_allowed_now: bool,
    entry_status: EntryStatus,
) -> DiscoverySetup:
    return DiscoverySetup(
        candidate_id=candidate_id,
        symbol="BTCUSDT",
        strategy=StrategyType.BREAKOUT_RETEST,
        direction=TradeDirection.LONG,
        decision_time=datetime(2026, 7, 20, 12, tzinfo=UTC),
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
        stop_loss=StopLoss(
            price=95.0,
            distance=5.0,
            distance_pct=5.0,
            rationale=("structure",),
        ),
        take_profits=(
            TakeProfit(
                label="TP1",
                price=110.0,
                reward=10.0,
                risk_reward=2.0,
                rationale=("target",),
            ),
        ),
        management_policies=(
            ManagementPolicy(
                kind=ManagementPolicyType.TIME_EXIT,
                trigger="holding window ends",
                action="exit",
                rationale=("bounded replay",),
            ),
        ),
        confidence_score=80.0,
        execution_allowed_now=execution_allowed_now,
        entry_status=entry_status,
        canonical_actionability=False,
        layered_state=LayeredStateSnapshot(
            execution_state=ExecutionState.CLEAN,
            setup_state=SetupState.BREAKOUT_RETEST,
            context_state=ContextState.TRENDING_UP,
            structural_bias=StructuralBias.BULLISH,
            risk_condition=RiskCondition.NORMAL,
            timeframe_relationship=TimeframeRelationship.WITH_TREND,
            relationship_severity=RelationshipSeverity.NONE,
            holding_horizon=HoldingHorizon.INTRADAY,
            continuation_state=ContinuationState.FRESH_CONTINUATION,
        ),
        methodology_scores=ScoreDimensions(
            pattern_confidence=80.0,
            directional_alignment=82.0,
            setup_quality=84.0,
            execution_quality=86.0,
            reward_quality=88.0,
            timing_quality=90.0,
            data_confidence=92.0,
            overall_trade_quality=85.0,
            rank_score=87.0,
        ),
    )


def _analysis(*opportunities: object, legacy_setup: DiscoverySetup | None = None) -> object:
    return SimpleNamespace(
        opportunity_portfolio=SimpleNamespace(opportunities=opportunities),
        assessment=SimpleNamespace(setup=legacy_setup, reasons=("legacy reason",)),
    )


def test_selects_executable_current_canonical_opportunity() -> None:
    legacy = _setup(
        "legacy",
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )
    canonical = _setup(
        "canonical",
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )
    opportunity = SimpleNamespace(
        opportunity_id="canonical",
        setup=canonical,
        sequence_role=SequenceRole.CURRENT,
        effective_lane=OpportunityLane.CMP_SCALP,
    )

    decision = backtesting._select_replay_decision(_analysis(opportunity, legacy_setup=legacy))

    assert decision.setup is canonical
    assert decision.opportunity_id == "canonical"
    assert decision.sequence_role == "current"
    assert decision.lane == "cmp_scalp"
    assert decision.actionability_state == "execute_now"
    assert decision.reason_code == "canonical_executable_opportunity"
    assert decision.canonical_portfolio is True


def test_pending_canonical_opportunity_is_not_fabricated_into_signal() -> None:
    nearby = _setup(
        "nearby",
        execution_allowed_now=False,
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
    )
    opportunity = SimpleNamespace(
        opportunity_id="nearby",
        setup=nearby,
        sequence_role=SequenceRole.NEARBY,
    )

    decision = backtesting._select_replay_decision(_analysis(opportunity))

    assert decision.setup is None
    assert decision.reason_code == "canonical_opportunity_pending_activation"
    assert decision.canonical_portfolio is True


def test_pending_conditional_opportunity_is_selected_for_diagnostic_replay() -> None:
    base = _setup(
        "conditional",
        execution_allowed_now=False,
        entry_status=EntryStatus.CONFIRMATION_AT_CMP,
    )
    pending = replace(
        base,
        conditional_plan=ConditionalExecutionPlan(
            trigger=ActivationTrigger(
                kind=ActivationTriggerType.CANDLE_CLOSE,
                level=100.0,
                condition="close through trigger",
            ),
            pre_entry_invalidation=PreEntryInvalidation(
                price=95.0,
                condition="touch invalidation",
                rationale=("structure failed",),
            ),
            conditional_order_eligible=False,
            recommended_order_intent=RecommendedOrderIntent.ALERT_ONLY,
            reason_not_executable_now="confirmation incomplete",
            geometry_basis="preferred entry",
            entry_source="strategy trigger",
            trigger_matches_preferred_entry=True,
            stop_basis="structural stop",
            targets_basis="structural targets",
            geometry_is_trigger_relative=True,
        ),
    )
    opportunity = SimpleNamespace(
        opportunity_id="conditional",
        setup=pending,
        sequence_role=SequenceRole.CURRENT,
        effective_lane=OpportunityLane.CONFIRMATION_SCALP,
    )

    decision = backtesting._select_replay_decision(_analysis(opportunity))

    assert decision.setup is pending
    assert decision.execution_authorized is False
    assert decision.reason_code == "canonical_opportunity_pending_activation"
    assert decision.actionability_state is not None


def test_legacy_setup_is_used_only_when_portfolio_is_absent() -> None:
    legacy = _setup(
        "legacy",
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )
    analysis = SimpleNamespace(
        opportunity_portfolio=None,
        assessment=SimpleNamespace(setup=legacy, reasons=()),
    )

    decision = backtesting._select_replay_decision(analysis)

    assert decision.setup is legacy
    assert decision.opportunity_id == "legacy"
    assert decision.reason_code == "legacy_selected_setup"
    assert decision.canonical_portfolio is False


def test_calibration_record_preserves_methodology_dimensions(monkeypatch) -> None:
    setup = _setup(
        "canonical",
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )
    decision = backtesting._ReplayDecision(
        setup=setup,
        opportunity_id="canonical",
        sequence_role="current",
        lane="cmp_scalp",
        actionability_state="execute_now",
        reason_code="canonical_executable_opportunity",
        canonical_portfolio=True,
    )
    analysis = SimpleNamespace(
        assessment=SimpleNamespace(reasons=()),
        opportunity_portfolio=None,
    )
    monkeypatch.setattr(
        backtesting,
        "serialize_symbol_analysis",
        lambda _analysis: {
            "symbol": "BTCUSDT",
            "generated_at": "2026-07-20T12:00:00+00:00",
            "decision": "long",
            "methodology_version": "test-methodology",
            "reasons": [],
            "phase5_diagnostics": {},
        },
    )

    record = backtesting._calibration_record(
        analysis=analysis,
        partition="final_test",
        replay_decision=decision,
    )

    assert record["lane"] == "cmp_scalp"
    assert record["methodology_version"] == "test-methodology"
    assert record["layered_state"] == setup.layered_state.to_dict()
    assert record["score_components"] == setup.methodology_scores.to_dict()
    assert record["continuation_state"] == "fresh_continuation"
    assert record["target_basis"] == ["strategy_supplied_structural_level"]
    assert record["runner_qualified"] is False
    assert record["rejection_reason"] is None


def test_live_snapshot_and_backtest_selection_preserve_canonical_decision() -> None:
    live_setup = _setup(
        "closed-candle-canonical",
        execution_allowed_now=True,
        entry_status=EntryStatus.READY_NOW,
    )
    opportunity = SimpleNamespace(
        opportunity_id="closed-candle-canonical",
        setup=live_setup,
        sequence_role=SequenceRole.CURRENT,
        effective_lane=OpportunityLane.CMP_SCALP,
    )
    live_analysis = _analysis(opportunity)

    replay = backtesting._select_replay_decision(live_analysis)

    assert replay.setup is live_setup
    assert replay.opportunity_id == live_setup.candidate_id
    assert replay.sequence_role == SequenceRole.CURRENT.value
    assert replay.lane == OpportunityLane.CMP_SCALP.value
    assert replay.actionability_state == "execute_now"
    assert replay.setup.direction is live_setup.direction
    assert replay.setup.strategy is live_setup.strategy
    assert replay.setup.entry == live_setup.entry
    assert replay.setup.stop_loss == live_setup.stop_loss
    assert replay.setup.take_profits == live_setup.take_profits
    assert replay.setup.layered_state == live_setup.layered_state
    assert replay.setup.methodology_scores == live_setup.methodology_scores
