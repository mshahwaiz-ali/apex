from __future__ import annotations

from datetime import UTC, datetime

from apex.application.discovery_analysis import _setup_payload
from apex.application.discovery_contracts import (
    ActionableEntry,
    DiscoverySetup,
    ManagementPolicy,
    ManagementPolicyType,
    StopLoss,
    TakeProfit,
)
from apex.presentation.operator_output import render_analysis
from apex.strategies.contracts import EntryMode, TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType

NOW = datetime(2026, 7, 20, tzinfo=UTC)


def _setup(
    *,
    entry_mode: EntryMode,
    confirmation_complete: bool,
    execution_allowed_now: bool = False,
) -> DiscoverySetup:
    return DiscoverySetup(
        symbol="BTCUSDT",
        direction=TradeDirection.LONG,
        strategy=StrategyType.BREAKOUT_CONTINUATION,
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
        decision_time=NOW,
        candidate_id="candidate",
        confidence_score=75.0,
        entry=ActionableEntry(
            lower=99.0,
            upper=101.0,
            preferred=100.0,
            current_price=100.0,
            maximum_chase_price=102.0,
            current_price_inside_zone=True,
        ),
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
        execution_allowed_now=execution_allowed_now,
        entry_mode=entry_mode,
        confirmation_required=not confirmation_complete,
        confirmation_complete=confirmation_complete,
        canonical_actionability=True,
    )


def _analysis_payload(setup_payload: dict[str, object]) -> dict[str, object]:
    return {
        "symbol": "BTCUSDT",
        "setup": setup_payload,
        "developing_setup": None,
        "focused_analysis": {},
        "reasons": [],
    }


def test_setup_payload_exposes_canonical_actionability() -> None:
    payload = _setup_payload(
        _setup(
            entry_mode=EntryMode.RETEST,
            confirmation_complete=False,
        )
    )

    assert payload["actionability_state"] == "execute_on_micro_confirmation"
    assert payload["actionability_basis"] == "micro_confirmation_inside_zone"
    assert payload["sequence_role"] == "current"
    assert payload["entry_status"] == "WATCH_NEAR_ENTRY"
    assert payload["execution_allowed_now"] is False


def test_operator_output_uses_micro_confirmation_not_legacy_execution_flag() -> None:
    setup_payload = _setup_payload(
        _setup(
            entry_mode=EntryMode.RETEST,
            confirmation_complete=False,
        )
    )

    rendered = render_analysis(_analysis_payload(setup_payload))

    assert "WAIT FOR MICRO CONFIRMATION" in rendered
    assert "Actionability" in rendered
    assert "Execute on micro confirmation" in rendered
    assert "ENTER LONG" not in rendered


def test_operator_output_enters_aggressive_current_setup() -> None:
    setup_payload = _setup_payload(
        _setup(
            entry_mode=EntryMode.MARKET_NEAR,
            confirmation_complete=False,
        )
    )

    rendered = render_analysis(_analysis_payload(setup_payload))

    assert "ENTER LONG" in rendered
    assert "Aggressive now" in rendered
