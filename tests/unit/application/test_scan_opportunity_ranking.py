"""Tests for scanner-wide opportunity ranking and display limits."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

from apex.application.decision_analysis import (
    DEFAULT_SCAN_DISPLAY_LIMIT,
    _display_analyses,
    _scan_sort_key,
)
from apex.application.analysis import ScanResult


def _analysis(
    symbol: str,
    *,
    final_rank_score: float | None,
    approved: bool,
) -> Any:
    record = (
        None
        if final_rank_score is None
        else SimpleNamespace(rank=1, final_rank_score=final_rank_score)
    )
    ranking = SimpleNamespace(
        primary=record if approved else None,
        alternatives=(),
        rejected=() if approved or record is None else (record,),
    )
    return SimpleNamespace(
        symbol=symbol,
        assessment=SimpleNamespace(setup=object() if approved else None),
        candidate_ranking=ranking,
    )


def test_scanner_sort_uses_best_candidate_rank_score_not_approval_first() -> None:
    approved_lower = _analysis(
        "APPROVED",
        final_rank_score=62.0,
        approved=True,
    )
    rejected_higher = _analysis(
        "REJECTED",
        final_rank_score=81.0,
        approved=False,
    )

    ordered = sorted((approved_lower, rejected_higher), key=_scan_sort_key)

    assert [item.symbol for item in ordered] == ["REJECTED", "APPROVED"]


def test_scanner_sort_places_symbols_without_candidates_last() -> None:
    candidate = _analysis("CANDIDATE", final_rank_score=40.0, approved=False)
    empty = _analysis("EMPTY", final_rank_score=None, approved=False)

    ordered = sorted((empty, candidate), key=_scan_sort_key)

    assert [item.symbol for item in ordered] == ["CANDIDATE", "EMPTY"]


def test_default_display_retains_only_top_fifteen_without_mutating_result() -> None:
    analyses = tuple(
        _analysis(
            f"SYMBOL-{index:02d}",
            final_rank_score=float(100 - index),
            approved=False,
        )
        for index in range(20)
    )
    result = ScanResult(
        generated_at=cast(Any, None),
        analyses=cast(Any, analyses),
        failures={},
    )

    displayed = _display_analyses(result)

    assert DEFAULT_SCAN_DISPLAY_LIMIT == 15
    assert len(displayed) == 15
    assert len(result.analyses) == 20
    assert displayed == analyses[:15]
