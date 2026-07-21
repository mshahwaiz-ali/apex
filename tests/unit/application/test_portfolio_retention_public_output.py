from __future__ import annotations

from dataclasses import replace

from tests.unit.scoring.test_quality_shadow_rollout import _selection

from apex.application.discovery_setup import build_discovery_assessment
from apex.application.opportunity_portfolio import (
    AnalysisMode,
    opportunity_portfolio_payload,
    portfolio_from_setups,
)


def _setup():
    assessment = build_discovery_assessment(_selection())
    assert assessment.setup is not None
    return assessment.setup


def test_live_portfolio_payload_exposes_retention_diagnostics() -> None:
    setup = _setup()
    weaker = replace(setup, candidate_id="weaker", confidence_score=60.0)
    stronger = replace(setup, candidate_id="stronger", confidence_score=90.0)

    portfolio = portfolio_from_setups(
        (weaker, stronger),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    payload = opportunity_portfolio_payload(portfolio)

    diagnostics = payload["retention_diagnostics"]
    assert isinstance(diagnostics, dict)
    assert diagnostics["candidate_count"] == 2
    assert diagnostics["retained_count"] == 1
    assert diagnostics["suppressed_count"] == 1
    assert diagnostics["retained_candidate_ids"] == ["stronger"]
    assert diagnostics["suppressed_candidate_ids"] == ["weaker"]


def test_suppressed_record_names_retained_candidate_and_reason() -> None:
    setup = _setup()
    weaker = replace(setup, candidate_id="weaker", confidence_score=60.0)
    stronger = replace(setup, candidate_id="stronger", confidence_score=90.0)

    portfolio = portfolio_from_setups(
        (weaker, stronger),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.SCAN_CMP_FIRST,
    )
    payload = opportunity_portfolio_payload(portfolio)
    diagnostics = payload["retention_diagnostics"]
    assert isinstance(diagnostics, dict)
    records = diagnostics["records"]
    assert isinstance(records, list)

    weaker_record = next(record for record in records if record["candidate_id"] == "weaker")
    assert weaker_record["retained"] is False
    assert weaker_record["suppression_reason"] == "duplicate_geometry"
    assert weaker_record["retained_candidate_id"] == "stronger"


def test_retained_record_has_no_suppression_reason() -> None:
    setup = _setup()
    portfolio = portfolio_from_setups(
        (setup,),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    diagnostics = opportunity_portfolio_payload(portfolio)["retention_diagnostics"]
    assert isinstance(diagnostics, dict)
    record = diagnostics["records"][0]

    assert record["retained"] is True
    assert record["suppression_reason"] is None
    assert record["retained_candidate_id"] is None


def test_legacy_portfolio_without_audit_serializes_unavailable_diagnostics() -> None:
    setup = _setup()
    portfolio = portfolio_from_setups(
        (setup,),
        symbol=setup.symbol,
        cmp=setup.entry.current_price,
        analysis_timestamp=setup.decision_time,
        analysis_mode=AnalysisMode.ANALYZE_FULL,
    )
    legacy_like = replace(portfolio, retention_diagnostics=None)

    payload = opportunity_portfolio_payload(legacy_like)

    assert payload["retention_diagnostics"] is None
