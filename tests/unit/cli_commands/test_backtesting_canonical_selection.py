from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.application.opportunity_portfolio import SequenceRole
from apex.cli_commands import backtesting
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
    )

    decision = backtesting._select_replay_decision(_analysis(opportunity, legacy_setup=legacy))

    assert decision.setup is canonical
    assert decision.opportunity_id == "canonical"
    assert decision.sequence_role == "current"
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
