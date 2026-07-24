from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from apex.application.hierarchical_timeframe_routing import (
    ParentThesisState,
    child_timeframe_lineage,
    derive_parent_timeframe_thesis_from_frames,
    is_hierarchical_pre_entry_candidate,
)
from apex.strategies.context import TimeframeContext, TimeframeRole
from apex.strategies.contracts import TradeDirection
from apex.strategies.entry_status import EntryStatus
from apex.structure.contracts import TrendDirection


def _frame(
    timeframe: str,
    role: TimeframeRole,
    direction: TrendDirection,
) -> TimeframeContext:
    return cast(
        TimeframeContext,
        SimpleNamespace(
            timeframe=timeframe,
            role=role,
            structure=SimpleNamespace(
                trend=SimpleNamespace(direction=direction),
            ),
        ),
    )


def test_agreeing_30m_and_15m_establish_parent_long_thesis() -> None:
    thesis = derive_parent_timeframe_thesis_from_frames(
        (
            _frame("30m", TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame("15m", TimeframeRole.SETUP, TrendDirection.STRONG_BULLISH),
            _frame("5m", TimeframeRole.ENTRY, TrendDirection.WEAK_BEARISH),
        )
    )

    assert thesis.state is ParentThesisState.ESTABLISHED
    assert thesis.direction is TradeDirection.LONG
    assert thesis.parent_timeframes == ("30m", "15m")
    assert thesis.execution_timeframe == "5m"
    assert thesis.enforces_direction is True


def test_parent_disagreement_does_not_force_direction() -> None:
    thesis = derive_parent_timeframe_thesis_from_frames(
        (
            _frame("30m", TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame("15m", TimeframeRole.SETUP, TrendDirection.BEARISH),
            _frame("5m", TimeframeRole.ENTRY, TrendDirection.BULLISH),
        )
    )

    assert thesis.state is ParentThesisState.CONFLICT
    assert thesis.direction is None
    assert thesis.enforces_direction is False


def test_one_directional_parent_and_one_neutral_is_developing() -> None:
    thesis = derive_parent_timeframe_thesis_from_frames(
        (
            _frame("30m", TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame("15m", TimeframeRole.SETUP, TrendDirection.RANGE),
            _frame("5m", TimeframeRole.ENTRY, TrendDirection.BULLISH),
        )
    )

    assert thesis.state is ParentThesisState.DEVELOPING
    assert thesis.direction is TradeDirection.LONG
    assert thesis.enforces_direction is False


def test_child_lineage_uses_15m_for_setup_and_5m_for_execution() -> None:
    thesis = derive_parent_timeframe_thesis_from_frames(
        (
            _frame("30m", TimeframeRole.INTRADAY, TrendDirection.BULLISH),
            _frame("15m", TimeframeRole.SETUP, TrendDirection.BULLISH),
            _frame("5m", TimeframeRole.ENTRY, TrendDirection.WEAK_BEARISH),
        )
    )

    lineage = child_timeframe_lineage(thesis)

    assert lineage == {
        "setup_timeframe": "15m",
        "execution_timeframe": "5m",
        "confirmation_timeframe": "5m",
        "invalidation_timeframe": "15m",
        "target_timeframe": "30m",
    }


def test_established_child_waiting_state_is_pre_entry_visible() -> None:
    candidate = cast(
        object,
        SimpleNamespace(
            metadata={
                "parent_thesis_state": "established",
                "hierarchical_child_entry_search": 1,
                "parent_thesis_waiting_for_child_trigger": 1,
            }
        ),
    )

    assert is_hierarchical_pre_entry_candidate(
        candidate,  # type: ignore[arg-type]
        entry_status=EntryStatus.WATCH_NEAR_ENTRY,
    )


def test_invalidated_child_is_not_pre_entry_visible() -> None:
    candidate = cast(
        object,
        SimpleNamespace(
            metadata={
                "parent_thesis_state": "established",
                "hierarchical_child_entry_search": 1,
                "parent_thesis_waiting_for_child_trigger": 1,
            }
        ),
    )

    assert not is_hierarchical_pre_entry_candidate(
        candidate,  # type: ignore[arg-type]
        entry_status=EntryStatus.INVALIDATED,
    )
