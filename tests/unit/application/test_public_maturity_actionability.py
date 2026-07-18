from __future__ import annotations

import pytest

from apex.application.methodology_setup_maturity import SetupMaturityAssessment
from apex.application.methodology_strategy_contracts import (
    ConfirmationPolicy,
    SetupMaturity,
)
from apex.application.public_output import _result_group, _selected_reason_code
from apex.strategies.entry_status import EntryStatus
from apex.strategies.strategy_types import StrategyType


def _maturity(
    maturity: SetupMaturity,
    *,
    complete: bool,
    code: str,
    status: EntryStatus = EntryStatus.READY_NOW,
) -> SetupMaturityAssessment:
    return SetupMaturityAssessment(
        strategy=StrategyType.MOMENTUM_BREAKOUT,
        legacy_status=status,
        maturity=maturity,
        confirmation_policy=ConfirmationPolicy.CLOSE_REQUIRED,
        execution_conditions_complete=complete,
        reason_codes=(code,),
        reasons=("test maturity state",),
    )


def test_pending_confirmation_is_developing_not_actionable() -> None:
    maturity = _maturity(
        SetupMaturity.CONFIRMATION_PENDING_CLOSE,
        complete=False,
        code="METHODOLOGY_CONFIRMATION_STILL_REQUIRED",
    )

    assert _result_group(maturity) == "developing"
    assert _selected_reason_code(maturity, EntryStatus.READY_NOW) == (
        "METHODOLOGY_CONFIRMATION_STILL_REQUIRED"
    )


def test_completed_execution_is_actionable() -> None:
    maturity = _maturity(
        SetupMaturity.ENTRY_AVAILABLE,
        complete=True,
        code="METHODOLOGY_ENTRY_AVAILABLE",
    )

    assert _result_group(maturity) == "actionable"
    assert _selected_reason_code(maturity, EntryStatus.READY_NOW) == "READY_NOW"


@pytest.mark.parametrize(
    "state",
    [
        SetupMaturity.ENTRY_LATE,
        SetupMaturity.ENTRY_MISSED,
        SetupMaturity.PATTERN_FAILED,
        SetupMaturity.INVALIDATED,
    ],
)
def test_terminal_or_late_maturity_is_unavailable(state: SetupMaturity) -> None:
    maturity = _maturity(
        state,
        complete=False,
        code="METHODOLOGY_SETUP_UNAVAILABLE",
        status=EntryStatus.LATE_OR_CHASING,
    )

    assert _result_group(maturity) == "unavailable"


def test_missing_selected_maturity_is_no_trade() -> None:
    assert _result_group(None) == "no_trade"
    assert _selected_reason_code(None, "NO_TRADE") == "NO_TRADE"
