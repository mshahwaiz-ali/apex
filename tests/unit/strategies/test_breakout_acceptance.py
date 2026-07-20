from __future__ import annotations

import pytest

from apex.strategies.breakout_acceptance import (
    BreakoutAcceptancePolicy,
    BreakoutAcceptanceState,
    BreakoutBarObservation,
    audit_breakout_acceptance,
)
from apex.strategies.contracts import TradeDirection


def _bar(
    close: float,
    *,
    high: float | None = None,
    low: float | None = None,
    duration_seconds: int = 60,
    closed: bool = True,
) -> BreakoutBarObservation:
    return BreakoutBarObservation(
        close=close,
        high=high if high is not None else close + 1.0,
        low=low if low is not None else close - 1.0,
        duration_seconds=duration_seconds,
        closed=closed,
    )


POLICY = BreakoutAcceptancePolicy(
    minimum_consecutive_closes=2,
    minimum_acceptance_seconds=120,
    maximum_reentry_fraction=0.0,
)


def test_long_breakout_is_accepted_after_required_closes_and_time() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            _bar(101.0),
            _bar(102.0),
        ),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.ACCEPTED
    assert audit.consecutive_closes == 2
    assert audit.acceptance_seconds == 120
    assert audit.accepted is True


def test_short_breakout_is_directionally_symmetric() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.SHORT,
        100.0,
        (
            _bar(99.0),
            _bar(98.0),
        ),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.ACCEPTED
    assert audit.consecutive_closes == 2


def test_single_close_beyond_level_is_provisional() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (_bar(101.0),),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.PROVISIONAL
    assert audit.consecutive_closes == 1


def test_intrabar_touch_without_close_acceptance_is_rejected() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            _bar(99.5, high=101.0, low=99.0),
            _bar(99.0, high=100.5, low=98.5),
        ),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.REJECTED
    assert audit.consecutive_closes == 0


def test_level_never_touched_is_not_broken() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            _bar(98.0, high=99.0, low=97.0),
            _bar(99.0, high=99.5, low=98.0),
        ),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.NOT_BROKEN


def test_reentry_fraction_can_reject_otherwise_positive_sequence() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            _bar(99.5, high=101.0, low=99.0),
            _bar(101.0),
            _bar(102.0),
        ),
        policy=BreakoutAcceptancePolicy(
            minimum_consecutive_closes=2,
            minimum_acceptance_seconds=120,
            maximum_reentry_fraction=0.25,
        ),
    )

    assert audit.reentry_fraction == pytest.approx(1 / 3)
    assert audit.state is BreakoutAcceptanceState.REJECTED


def test_open_bar_is_ignored_for_acceptance() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (
            _bar(101.0),
            _bar(102.0, closed=False),
        ),
        policy=POLICY,
    )

    assert audit.evaluated_closed_bars == 1
    assert audit.state is BreakoutAcceptanceState.PROVISIONAL


def test_no_closed_bars_returns_not_broken() -> None:
    audit = audit_breakout_acceptance(
        TradeDirection.LONG,
        100.0,
        (_bar(102.0, closed=False),),
        policy=POLICY,
    )

    assert audit.state is BreakoutAcceptanceState.NOT_BROKEN
    assert audit.evaluated_closed_bars == 0


def test_policy_rejects_invalid_reentry_fraction() -> None:
    with pytest.raises(
        ValueError,
        match="maximum reentry fraction must be between zero and one",
    ):
        BreakoutAcceptancePolicy(maximum_reentry_fraction=1.1)


def test_bar_rejects_close_outside_range() -> None:
    with pytest.raises(
        ValueError,
        match="bar close must lie inside the bar range",
    ):
        BreakoutBarObservation(
            close=102.0,
            high=101.0,
            low=99.0,
            duration_seconds=60,
        )
