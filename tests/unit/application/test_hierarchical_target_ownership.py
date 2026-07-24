from __future__ import annotations

from types import SimpleNamespace
from typing import cast

from apex.application.discovery_setup import _target_timeframe_for_level
from apex.strategies.contracts import TargetType, TradeCandidate


def _candidate(metadata: dict[str, str | int | float]) -> TradeCandidate:
    return cast(TradeCandidate, SimpleNamespace(metadata=metadata))


def test_hierarchical_tp1_uses_setup_timeframe() -> None:
    candidate = _candidate(
        {
            "hierarchical_child_entry_search": 1,
            "setup_timeframe": "15m",
            "target_timeframe": "30m",
        }
    )

    assert (
        _target_timeframe_for_level(
            candidate,
            kind=TargetType.STRUCTURAL,
            label="TP1",
        )
        == "15m"
    )


def test_hierarchical_expansion_uses_broader_target_timeframe() -> None:
    candidate = _candidate(
        {
            "hierarchical_child_entry_search": 1,
            "setup_timeframe": "15m",
            "target_timeframe": "30m",
        }
    )

    assert (
        _target_timeframe_for_level(
            candidate,
            kind=TargetType.EXPANSION,
            label="TP3",
        )
        == "30m"
    )


def test_legacy_candidate_preserves_existing_target_fallback() -> None:
    candidate = _candidate(
        {
            "setup_timeframe": "15m",
            "target_timeframe": "30m",
        }
    )

    assert (
        _target_timeframe_for_level(
            candidate,
            kind=TargetType.STRUCTURAL,
            label="TP1",
        )
        == "30m"
    )


def test_hierarchical_tp1_uses_setup_timeframe_even_when_child_direction_is_not_enforced() -> None:
    candidate = _candidate(
        {
            "parent_thesis_state": "conflict",
            "hierarchical_child_entry_search": 0,
            "execution_timeframe": "5m",
            "setup_timeframe": "15m",
            "target_timeframe": "30m",
        }
    )

    assert (
        _target_timeframe_for_level(
            candidate,
            kind=TargetType.STRUCTURAL,
            label="TP1",
        )
        == "15m"
    )
