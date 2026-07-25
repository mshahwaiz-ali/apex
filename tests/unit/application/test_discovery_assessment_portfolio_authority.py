from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from apex.application import discovery_setup
from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.scoring.contracts import CandidateOutcome
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 25, tzinfo=UTC)


def _setup(
    candidate_id: str,
    *,
    executable: bool,
    confidence: float,
    current_price: float = 100.0,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.READY_NOW if executable else EntryStatus.PULLBACK_PREFERRED,
        decision_time=NOW,
        candidate_id=candidate_id,
        confidence_score=confidence,
        entry=ActionableEntry(
            99.0 if executable else current_price - 4.0,
            101.0 if executable else current_price - 2.0,
            100.0 if executable else current_price - 3.0,
            current_price,
            102.0 if executable else current_price - 1.0,
            executable,
        ),
        stop_loss=StopLoss(94.0, 6.0, 6.0, ("structure",)),
        take_profits=(TakeProfit("TP1", 112.0, 12.0, 2.0, ("structure",)),),
        management_policies=(
            ManagementPolicy(
                ManagementPolicyType.TIME_EXIT,
                "expiry",
                "cancel",
                ("stale",),
            ),
        ),
        execution_allowed_now=executable,
    )


def _selection(*items: SimpleNamespace) -> SimpleNamespace:
    return SimpleNamespace(
        symbol="BTCUSDT",
        decision_time=NOW,
        ranked_candidates=items,
        selected_candidate=items[-1],
        selected_future_candidate=None,
        no_trade_reason=None,
    )


def test_assessment_uses_canonical_executable_portfolio_opportunity(monkeypatch) -> None:
    executable = _setup("canonical-executable", executable=True, confidence=60.0)
    legacy_selected = _setup("legacy-selected-future", executable=False, confidence=99.0)
    items = (
        SimpleNamespace(
            outcome=CandidateOutcome.ACCEPTED,
            key="canonical-executable",
        ),
        SimpleNamespace(
            outcome=CandidateOutcome.ACCEPTED,
            key="legacy-selected-future",
        ),
    )
    setups = {
        "canonical-executable": executable,
        "legacy-selected-future": legacy_selected,
    }
    monkeypatch.setattr(discovery_setup, "_build_setup", lambda item: setups[item.key])
    monkeypatch.setattr(
        discovery_setup,
        "build_quality_shadow_rollout_diagnostics",
        lambda selection: SimpleNamespace(to_dict=lambda: {}),
    )

    assessment = discovery_setup.build_discovery_assessment(_selection(*items))

    assert assessment.setup is not None
    assert assessment.setup.candidate_id == "canonical-executable"
    assert assessment.developing_setup is not None
    assert assessment.developing_setup.candidate_id == "legacy-selected-future"


def test_assessment_uses_portfolio_primary_when_no_setup_is_executable(monkeypatch) -> None:
    stronger = _setup(
        "stronger-future",
        executable=False,
        confidence=85.0,
        current_price=100.0,
    )
    weaker = _setup(
        "weaker-future",
        executable=False,
        confidence=65.0,
        current_price=102.0,
    )
    items = (
        SimpleNamespace(outcome=CandidateOutcome.ACCEPTED, key="weaker-future"),
        SimpleNamespace(outcome=CandidateOutcome.ACCEPTED, key="stronger-future"),
    )
    setups = {
        "stronger-future": stronger,
        "weaker-future": weaker,
    }
    monkeypatch.setattr(discovery_setup, "_build_setup", lambda item: setups[item.key])
    monkeypatch.setattr(
        discovery_setup,
        "build_quality_shadow_rollout_diagnostics",
        lambda selection: SimpleNamespace(to_dict=lambda: {}),
    )

    assessment = discovery_setup.build_discovery_assessment(_selection(*items))

    assert assessment.setup is not None
    assert assessment.setup.candidate_id == "stronger-future"
    assert assessment.developing_setup is not None
    assert assessment.developing_setup.candidate_id == "weaker-future"
