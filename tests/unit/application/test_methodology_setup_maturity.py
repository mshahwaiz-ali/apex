from __future__ import annotations

import pytest

from apex.application.methodology_setup_maturity import (
    derive_setup_maturity,
    setup_maturity_payload,
)
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    SetupMaturity,
)
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


@pytest.mark.parametrize(
    ("strategy", "status", "maturity", "policy", "complete"),
    [
        (
            StrategyType.MOMENTUM_BREAKOUT,
            EntryStatus.READY_NOW,
            SetupMaturity.CONFIRMATION_PENDING_CLOSE,
            ConfirmationPolicy.CLOSE_REQUIRED,
            False,
        ),
        (
            StrategyType.MOMENTUM_SCALP,
            EntryStatus.AGGRESSIVE_NOW,
            SetupMaturity.ENTRY_AVAILABLE,
            ConfirmationPolicy.INTRABAR_ALLOWED,
            True,
        ),
        (
            StrategyType.BREAKOUT_RETEST,
            EntryStatus.READY_NOW,
            SetupMaturity.RETEST_PENDING,
            ConfirmationPolicy.RETEST_REQUIRED,
            False,
        ),
        (
            StrategyType.FAILED_BREAKOUT_REVERSAL,
            EntryStatus.READY_NOW,
            SetupMaturity.RECLAIM_PENDING,
            ConfirmationPolicy.RECLAIM_REQUIRED,
            False,
        ),
        (
            StrategyType.TREND_PULLBACK,
            EntryStatus.READY_NOW,
            SetupMaturity.ENTRY_AVAILABLE,
            ConfirmationPolicy.LOWER_TIMEFRAME_CONFIRMATION_ALLOWED,
            True,
        ),
        (
            StrategyType.RANGE_REVERSAL,
            EntryStatus.LATE_OR_CHASING,
            SetupMaturity.ENTRY_LATE,
            ConfirmationPolicy.MIXED,
            False,
        ),
        (
            StrategyType.EXHAUSTION_REVERSAL,
            EntryStatus.INVALIDATED,
            SetupMaturity.INVALIDATED,
            ConfirmationPolicy.CLOSE_REQUIRED,
            False,
        ),
    ],
)
def test_setup_maturity_respects_strategy_confirmation_policy(
    strategy: StrategyType,
    status: EntryStatus,
    maturity: SetupMaturity,
    policy: ConfirmationPolicy,
    complete: bool,
) -> None:
    assessment = derive_setup_maturity(strategy, status)

    assert assessment.maturity is maturity
    assert assessment.confirmation_policy is policy
    assert assessment.execution_conditions_complete is complete
    assert assessment.reason_codes
    assert assessment.reasons


def test_aggressive_entry_is_provisional_when_intrabar_execution_is_not_allowed() -> None:
    assessment = derive_setup_maturity(
        StrategyType.MOMENTUM_BREAKOUT,
        EntryStatus.AGGRESSIVE_NOW,
    )

    assert assessment.maturity is SetupMaturity.TRIGGER_PROVISIONAL
    assert assessment.execution_conditions_complete is False
    assert assessment.reason_codes == ("METHODOLOGY_AGGRESSIVE_TRIGGER_PROVISIONAL",)


def test_setup_maturity_payload_is_public_safe() -> None:
    payload = setup_maturity_payload(
        derive_setup_maturity(
            StrategyType.BREAKOUT_RETEST,
            EntryStatus.PULLBACK_PREFERRED,
        )
    )

    assert payload == {
        "strategy": "breakout_retest",
        "legacy_status": "PULLBACK_PREFERRED",
        "maturity": "retest_pending",
        "confirmation_policy": "retest_required",
        "execution_conditions_complete": False,
        "reason_codes": ["METHODOLOGY_BETTER_ENTRY_PENDING"],
        "reasons": [
            "a preferred nearby entry or strategy-specific confirmation remains pending"
        ],
    }
