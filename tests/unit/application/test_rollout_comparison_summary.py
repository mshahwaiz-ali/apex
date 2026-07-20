"""Tests for deterministic rollout comparison-set summaries."""

from __future__ import annotations

from apex.application.rollout_comparison import (
    AnalysisComparisonReport,
    DiagnosticDifference,
    NamedAnalysisComparison,
    comparison_summary_payload,
    summarize_analysis_comparisons,
)


def _report(
    *,
    symbol: str,
    differences: tuple[DiagnosticDifference, ...],
) -> AnalysisComparisonReport:
    return AnalysisComparisonReport(
        symbol=symbol,
        legacy_opportunity_count=1,
        new_opportunity_count=1,
        differences=differences,
    )


def test_summary_counts_matches_and_expected_compatibility_fields() -> None:
    comparisons = (
        NamedAnalysisComparison("fixture-match", _report(symbol="BTCUSDT", differences=())),
        NamedAnalysisComparison(
            "fixture-compatible",
            _report(
                symbol="ETHUSDT",
                differences=(
                    DiagnosticDifference("actionability_state", "AVAILABLE", "execute_now"),
                    DiagnosticDifference("confidence", 70.0, None),
                ),
            ),
        ),
    )

    summary = summarize_analysis_comparisons(comparisons)

    assert summary.total_count == 2
    assert summary.match_count == 1
    assert summary.difference_count == 1
    assert summary.compatibility_only_count == 1
    assert summary.regression_count == 0
    assert summary.field_difference_counts == {
        "actionability_state": 1,
        "confidence": 1,
    }
    assert summary.compatibility_fixture_ids == ("fixture-compatible",)
    assert summary.regression_fixture_ids == ()


def test_summary_marks_geometry_difference_as_regression() -> None:
    summary = summarize_analysis_comparisons(
        (
            NamedAnalysisComparison(
                "geometry-regression",
                _report(
                    symbol="SOLUSDT",
                    differences=(
                        DiagnosticDifference(
                            "entry_zone",
                            {"lower": 100.0, "upper": 101.0},
                            {"lower": 99.0, "upper": 101.0},
                        ),
                    ),
                ),
            ),
        )
    )

    assert summary.regression_count == 1
    assert summary.compatibility_only_count == 0
    assert summary.regression_fixture_ids == ("geometry-regression",)
    assert summary.regression_field_counts == {"entry_zone": 1}


def test_summary_mixed_report_is_regression_not_compatibility_only() -> None:
    summary = summarize_analysis_comparisons(
        (
            NamedAnalysisComparison(
                "mixed",
                _report(
                    symbol="XRPUSDT",
                    differences=(
                        DiagnosticDifference("actionability_state", "AVAILABLE", "execute_now"),
                        DiagnosticDifference("stop", 0.49, 0.48),
                    ),
                ),
            ),
        )
    )

    assert summary.regression_count == 1
    assert summary.compatibility_only_count == 0
    assert summary.regression_field_counts == {"stop": 1}


def test_summary_payload_is_non_authoritative_and_lists_affected_fixtures() -> None:
    summary = summarize_analysis_comparisons(
        (
            NamedAnalysisComparison(
                "compatibility",
                _report(
                    symbol="BTCUSDT",
                    differences=(DiagnosticDifference("ranking_score", 70.0, None),),
                ),
            ),
            NamedAnalysisComparison(
                "regression",
                _report(
                    symbol="ETHUSDT",
                    differences=(DiagnosticDifference("selected_strategy", "a", "b"),),
                ),
            ),
        )
    )

    payload = comparison_summary_payload(summary)

    assert payload["authoritative"] is False
    assert payload["compatibility_fixture_ids"] == ["compatibility"]
    assert payload["regression_fixture_ids"] == ["regression"]
    assert payload["regression_field_counts"] == {"selected_strategy": 1}


def test_empty_summary_is_stable() -> None:
    summary = summarize_analysis_comparisons(())

    assert summary.total_count == 0
    assert summary.match_count == 0
    assert summary.difference_count == 0
    assert summary.compatibility_only_count == 0
    assert summary.regression_count == 0
