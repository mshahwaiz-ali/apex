from __future__ import annotations

from apex.application.discovery_analysis import _candidate_pipeline_lineage


def test_geometry_rejections_are_accounted_separately_from_methodology_suppression() -> None:
    lineage = _candidate_pipeline_lineage(
        methodology_input_count=12,
        methodology_retained_count=12,
        methodology_suppressed_count=0,
        geometry_retained_count=6,
    )

    assert lineage == {
        "methodology_retained_candidate_count": 12,
        "geometry_rejected_candidate_count": 6,
        "methodology_lineage_balanced": True,
        "pipeline_lineage_balanced": True,
    }


def test_methodology_and_geometry_losses_balance_the_complete_pipeline() -> None:
    lineage = _candidate_pipeline_lineage(
        methodology_input_count=12,
        methodology_retained_count=9,
        methodology_suppressed_count=3,
        geometry_retained_count=5,
    )

    assert lineage["geometry_rejected_candidate_count"] == 4
    assert lineage["methodology_lineage_balanced"] is True
    assert lineage["pipeline_lineage_balanced"] is True
