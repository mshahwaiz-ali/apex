"""Tests for deterministic rollout acceptance policy."""

from __future__ import annotations

from apex.application.rollout_acceptance import (
    evaluate_rollout_acceptance,
    rollout_acceptance_payload,
)
from apex.application.rollout_comparison import AnalysisComparisonSummary


def _summary(
    *,
    total_count: int = 2,
    match_count: int = 1,
    compatibility_only_count: int = 1,
    regression_count: int = 0,
) -> AnalysisComparisonSummary:
    return AnalysisComparisonSummary(
        total_count=total_count,
        match_count=match_count,
        difference_count=total_count - match_count,
        compatibility_only_count=compatibility_only_count,
        regression_count=regression_count,
        field_difference_counts={},
        regression_field_counts={},
        compatibility_fixture_ids=(("compatibility",) if compatibility_only_count else ()),
        regression_fixture_ids=(("regression",) if regression_count else ()),
    )


def test_accepts_matches_and_compatibility_only_differences() -> None:
    result = evaluate_rollout_acceptance(_summary())

    assert result.accepted is True
    assert result.regression_count == 0
    assert result.compatibility_only_count == 1
    assert "allowed" in result.reasons[1]


def test_rejects_structural_regression_candidates() -> None:
    result = evaluate_rollout_acceptance(
        _summary(
            total_count=3,
            match_count=1,
            compatibility_only_count=1,
            regression_count=1,
        )
    )

    assert result.accepted is False
    assert result.regression_count == 1
    assert "structural regression" in result.reasons[0]


def test_payload_is_explicitly_non_authoritative() -> None:
    payload = rollout_acceptance_payload(evaluate_rollout_acceptance(_summary()))

    assert payload["accepted"] is True
    assert payload["authoritative"] is False
    assert "does not affect trade selection" in payload["interpretation"]


def test_empty_summary_is_accepted() -> None:
    result = evaluate_rollout_acceptance(
        _summary(
            total_count=0,
            match_count=0,
            compatibility_only_count=0,
            regression_count=0,
        )
    )

    assert result.accepted is True
    assert result.total_count == 0
