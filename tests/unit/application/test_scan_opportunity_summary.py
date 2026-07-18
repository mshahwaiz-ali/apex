"""Tests for operator-facing scanner opportunity summaries."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apex.application.decision_analysis import _opportunity_summary_lines


def _analysis(record: Any | None) -> Any:
    ranking = (
        None
        if record is None
        else SimpleNamespace(
            primary=None,
            alternatives=(),
            rejected=(record,),
        )
    )
    return SimpleNamespace(candidate_ranking=ranking)


def test_opportunity_summary_exposes_label_rank_score_and_dimensions() -> None:
    record = SimpleNamespace(
        rank=1,
        quality_label=SimpleNamespace(value="usable"),
        strategy="trend_pullback",
        direction="long",
        final_rank_score=72.5,
        rank_penalty_score=6.0,
        score_dimensions=SimpleNamespace(
            opportunity_score=80.0,
            setup_score=74.0,
            timing_score=68.0,
            trade_quality_score=61.0,
        ),
    )

    lines = _opportunity_summary_lines(_analysis(record))

    assert lines == (
        "Best opportunity: USABLE | trend_pullback LONG | rank score 72.5",
        (
            "Score profile: opportunity 80.0 | setup 74.0 | timing 68.0 | "
            "trade quality 61.0 | penalties 6.0"
        ),
    )


def test_opportunity_summary_handles_symbol_without_ranked_candidate() -> None:
    assert _opportunity_summary_lines(_analysis(None)) == ("Best opportunity: none",)
