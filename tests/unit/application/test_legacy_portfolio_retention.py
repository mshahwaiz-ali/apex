from __future__ import annotations

from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_contracts import DiscoveryAssessment
from apex.application.discovery_setup import build_discovery_assessment
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    portfolio_from_legacy_assessment,
)
from apex.strategies.entry_status import EntryStatus


def _assessment() -> DiscoveryAssessment:
    return build_discovery_assessment(_selection())


def test_rejected_legacy_setup_cannot_reenter_portfolio() -> None:
    assessment = _assessment()
    assert assessment.setup is not None
    invalidated = replace(
        assessment.setup,
        entry_status=EntryStatus.INVALIDATED,
        execution_allowed_now=False,
    )
    rejected = replace(
        assessment,
        setup=invalidated,
        developing_setup=None,
    )

    portfolio = portfolio_from_legacy_assessment(
        rejected,
        cmp=invalidated.entry.current_price,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.opportunities == ()
    assert portfolio.primary_opportunity is None


def test_legacy_adapter_uses_canonical_retention_diagnostics() -> None:
    assessment = _assessment()
    assert assessment.setup is not None
    weaker = replace(
        assessment.setup,
        candidate_id="weaker",
        confidence_score=60.0,
    )
    stronger = replace(
        assessment.setup,
        candidate_id="stronger",
        confidence_score=90.0,
        execution_allowed_now=False,
    )
    legacy = replace(
        assessment,
        setup=weaker,
        developing_setup=stronger,
    )

    portfolio = portfolio_from_legacy_assessment(
        legacy,
        cmp=weaker.entry.current_price,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert tuple(opportunity.opportunity_id for opportunity in portfolio.opportunities) == (
        "stronger",
    )
    assert portfolio.retention_diagnostics is not None
    assert portfolio.retention_diagnostics["retained_candidate_ids"] == ["stronger"]
    assert portfolio.retention_diagnostics["suppressed_candidate_ids"] == ["weaker"]


def test_legacy_adapter_does_not_bypass_duplicate_handling() -> None:
    assessment = _assessment()
    assert assessment.setup is not None
    current = replace(
        assessment.setup,
        candidate_id="current",
        confidence_score=90.0,
        execution_allowed_now=True,
        confirmation_required=False,
        confirmation_complete=True,
    )
    duplicate = replace(
        current,
        candidate_id="duplicate",
        confidence_score=70.0,
        execution_allowed_now=False,
    )
    legacy = replace(
        assessment,
        setup=current,
        developing_setup=duplicate,
    )

    portfolio = portfolio_from_legacy_assessment(
        legacy,
        cmp=current.entry.current_price,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )

    assert tuple(opportunity.opportunity_id for opportunity in portfolio.opportunities) == (
        "current",
    )


def test_empty_legacy_assessment_builds_empty_audited_portfolio() -> None:
    assessment = _assessment()
    empty = replace(
        assessment,
        setup=None,
        developing_setup=None,
        reasons=("no valid legacy setup",),
    )

    portfolio = portfolio_from_legacy_assessment(
        empty,
        cmp=100.0,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )

    assert portfolio.opportunities == ()
    assert portfolio.retention_diagnostics is not None
    assert portfolio.retention_diagnostics["candidate_count"] == 0
